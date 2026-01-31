#!/usr/bin/env python3
"""
Fine-tuning script for the expense classifier.

This script fine-tunes a pre-trained model using feedback data
collected from user corrections. It can be run periodically
(e.g., weekly) when enough new feedback examples accumulate.

Usage:
    python scripts/finetune_classifier.py --output-dir ./models/expense_classifier_v1
    python scripts/finetune_classifier.py --min-examples 100 --epochs 3

Requirements:
    - transformers >= 4.30.0
    - datasets >= 2.0.0
    - torch >= 2.0.0
    - PostgreSQL database with classification_feedback table

The script will:
1. Load feedback data from the database
2. Prepare training/validation datasets
3. Fine-tune the base model
4. Save the fine-tuned model
5. Mark used feedback as processed
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


async def load_training_data(min_examples: int = 50) -> list[dict]:
    """
    Load training data from classification_feedback table.

    Args:
        min_examples: Minimum number of examples required to proceed

    Returns:
        List of training examples

    Raises:
        ValueError: If not enough examples available
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from app.config import settings
    from app.storage.classification_feedback import export_training_dataset

    # Create async engine and session
    engine = create_async_engine(settings.async_database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        dataset = await export_training_dataset(db)

    if len(dataset) < min_examples:
        raise ValueError(
            f"Not enough training examples. Found {len(dataset)}, "
            f"need at least {min_examples}."
        )

    return dataset


def prepare_datasets(data: list[dict], test_size: float = 0.2):
    """
    Prepare training and validation datasets.

    Args:
        data: List of training examples
        test_size: Fraction of data for validation

    Returns:
        Tuple of (train_dataset, eval_dataset)
    """
    from datasets import Dataset
    from sklearn.model_selection import train_test_split

    # Split data
    train_data, eval_data = train_test_split(
        data, test_size=test_size, random_state=42
    )

    # Convert to HuggingFace datasets
    train_dataset = Dataset.from_list(train_data)
    eval_dataset = Dataset.from_list(eval_data)

    print(f"Training examples: {len(train_dataset)}")
    print(f"Validation examples: {len(eval_dataset)}")

    return train_dataset, eval_dataset


def get_label_mapping(data: list[dict]) -> tuple[dict, dict]:
    """
    Create label to ID mappings.

    Args:
        data: Training data with 'label' field

    Returns:
        Tuple of (label2id, id2label) dicts
    """
    labels = sorted(set(d["label"] for d in data))
    label2id = {label: idx for idx, label in enumerate(labels)}
    id2label = {idx: label for label, idx in label2id.items()}

    print(f"Labels ({len(labels)}): {labels}")

    return label2id, id2label


def tokenize_data(dataset, tokenizer, label2id: dict):
    """
    Tokenize dataset for training.

    Args:
        dataset: HuggingFace dataset
        tokenizer: Model tokenizer
        label2id: Label to ID mapping

    Returns:
        Tokenized dataset
    """

    def tokenize_function(examples):
        tokenized = tokenizer(
            examples["text"],
            padding="max_length",
            truncation=True,
            max_length=128,
        )
        tokenized["labels"] = [label2id[label] for label in examples["label"]]
        return tokenized

    return dataset.map(tokenize_function, batched=True)


def train_model(
    train_dataset,
    eval_dataset,
    model_name: str,
    output_dir: str,
    label2id: dict,
    id2label: dict,
    epochs: int = 3,
    batch_size: int = 16,
    learning_rate: float = 2e-5,
):
    """
    Fine-tune the classification model.

    Args:
        train_dataset: Training dataset
        eval_dataset: Validation dataset
        model_name: Base model name
        output_dir: Directory to save model
        label2id: Label to ID mapping
        id2label: ID to label mapping
        epochs: Number of training epochs
        batch_size: Training batch size
        learning_rate: Learning rate

    Returns:
        Trained model and trainer
    """
    import numpy as np
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
    )

    print(f"\nLoading base model: {model_name}")

    # Load tokenizer and model
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        num_labels=len(label2id),
        label2id=label2id,
        id2label=id2label,
    )

    # Tokenize datasets
    print("Tokenizing datasets...")
    train_tokenized = tokenize_data(train_dataset, tokenizer, label2id)
    eval_tokenized = tokenize_data(eval_dataset, tokenizer, label2id)

    # Define compute metrics function
    def compute_metrics(eval_pred):
        from sklearn.metrics import accuracy_score, f1_score

        predictions, labels = eval_pred
        predictions = np.argmax(predictions, axis=1)

        accuracy = accuracy_score(labels, predictions)
        f1 = f1_score(labels, predictions, average="weighted")

        return {"accuracy": accuracy, "f1": f1}

    # Training arguments
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=learning_rate,
        weight_decay=0.01,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        greater_is_better=True,
        logging_dir=f"{output_dir}/logs",
        logging_steps=10,
        report_to="none",  # Disable wandb/tensorboard
    )

    # Create trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_tokenized,
        eval_dataset=eval_tokenized,
        tokenizer=tokenizer,
        compute_metrics=compute_metrics,
    )

    # Train
    print("\nStarting training...")
    trainer.train()

    # Evaluate
    print("\nEvaluating model...")
    eval_results = trainer.evaluate()
    print(f"Evaluation results: {eval_results}")

    # Save model
    print(f"\nSaving model to {output_dir}")
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)

    # Save label mappings
    with open(f"{output_dir}/label_mapping.json", "w") as f:
        json.dump({"label2id": label2id, "id2label": id2label}, f, indent=2)

    return model, trainer


async def mark_feedback_as_used(feedback_ids: list, batch_id: str):
    """
    Mark feedback records as used for training.

    Args:
        feedback_ids: List of feedback IDs
        batch_id: Training batch identifier
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from app.config import settings
    from app.storage.classification_feedback import mark_as_used_for_training

    engine = create_async_engine(settings.async_database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        updated = await mark_as_used_for_training(db, feedback_ids, batch_id)
        await db.commit()
        print(f"Marked {updated} feedback records as used")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Fine-tune expense classifier with feedback data"
    )
    parser.add_argument(
        "--model",
        default="distilbert-base-multilingual-cased",
        help="Base model to fine-tune",
    )
    parser.add_argument(
        "--output-dir",
        default="./models/expense_classifier",
        help="Directory to save fine-tuned model",
    )
    parser.add_argument(
        "--min-examples",
        type=int,
        default=50,
        help="Minimum number of feedback examples required",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=3,
        help="Number of training epochs",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
        help="Training batch size",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=2e-5,
        help="Learning rate",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load data but don't train",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Expense Classifier Fine-tuning Script")
    print("=" * 60)
    print(f"Base model: {args.model}")
    print(f"Output directory: {args.output_dir}")
    print(f"Minimum examples: {args.min_examples}")
    print(f"Epochs: {args.epochs}")
    print(f"Batch size: {args.batch_size}")
    print(f"Learning rate: {args.learning_rate}")
    print("=" * 60)

    # Load training data
    print("\nLoading training data from database...")
    try:
        data = asyncio.run(load_training_data(args.min_examples))
        print(f"Loaded {len(data)} training examples")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if args.dry_run:
        print("\nDry run - not training")
        print(f"Would train on {len(data)} examples")
        sys.exit(0)

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Prepare datasets
    print("\nPreparing datasets...")
    train_dataset, eval_dataset = prepare_datasets(data)

    # Get label mappings
    label2id, id2label = get_label_mapping(data)

    # Train model
    model, trainer = train_model(
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        model_name=args.model,
        output_dir=str(output_dir),
        label2id=label2id,
        id2label=id2label,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
    )

    # Generate training batch ID
    batch_id = f"train_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Mark feedback as used (for future runs)
    # Note: This would need the actual feedback IDs from the database
    # For now, we just print a message
    print(f"\nTraining batch ID: {batch_id}")
    print(f"Model saved to: {output_dir}")
    print("\nTo use this model, update your config:")
    print(f'  CLASSIFIER_MODEL_NAME="{output_dir}"')

    print("\n" + "=" * 60)
    print("Fine-tuning complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()


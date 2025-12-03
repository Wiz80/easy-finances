# Receipt Test Fixtures

This directory contains sample receipt images and PDFs for testing the Receipt Parser.

## Adding Test Receipts

To test the receipt parser, add receipt files to this directory:

```bash
# Supported formats: .jpg, .jpeg, .png, .pdf
cp ~/Downloads/receipt_001.jpg tests/fixtures/receipts/
```

## Running Tests

```bash
# Test with all fixtures in this directory
python tests-manual/test_receipt_parser.py

# Test with a specific receipt
python tests-manual/test_receipt_parser.py path/to/receipt.jpg
```

## Sample Receipt Sources

You can find sample receipts from:
- Your own recent purchases (photos or scanned PDFs)
- Public receipt datasets (search "sample receipt images")
- Generated test receipts (restaurant POS simulators)

## Privacy Note

⚠️ **Do not commit real receipts with personal information to version control!**

- This directory is already in `.gitignore`
- Keep test receipts anonymized or use synthetic examples
- Remove any credit card numbers, personal addresses, or identifying info


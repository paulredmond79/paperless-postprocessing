# Paperless Post-Processing Scripts

This project provides a set of Python scripts for post-processing documents in the [Paperless-ngx](https://github.com/paperless-ngx/paperless-ngx) document management system. These scripts automate tasks such as cleaning up correspondents, merging duplicates, and tagging documents.

## Features

- **Correspondent Management**:
  - Automatically checks for existing correspondents and creates new ones if necessary.
  - Cleans up correspondents with JSON names and updates them.
  - Merges duplicate correspondents and reassigns documents.

- **Tagging**:
  - Adds specific tags to documents, creating tags if they do not already exist.

- **Batch Processing**:
  - Processes all documents without a specific tag.

- **Custom Fields**:
  - Populates custom fields for documents using data fetched from the Paperless API.

- **OCR Data Utilization**:
  - Extracts metadata such as title, correspondent, and custom fields from OCR data.
  - Uses OpenAI to intelligently suggest or populate missing metadata fields, including document titles and correspondents.

## Project Structure

```
paperless-postprocessing
├── src
│   ├── post.py                  # Script for metadata extraction and updating documents
│   ├── postprocess.py           # Main logic for processing individual documents
│   ├── postprocess_all.py       # Processes all documents without a specific tag
│   ├── cleanup_correspondents.py # Cleans up correspondents with JSON names
│   ├── merge_duplicates.py      # Merges duplicate correspondents
│   └── utils
│       ├── api_helpers.py       # Helper functions for interacting with the Paperless API
│       └── __init__.py          # Marks the utils directory as a Python package
├── requirements.txt             # Lists project dependencies
├── README.md                    # Documentation for the project
└── .gitignore                   # Excludes unnecessary files from version control
```

## Setup Instructions

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd paperless-postprocessing
   ```

2. **Install Dependencies**
   It is recommended to use a virtual environment. You can create one using `venv` or `virtualenv`.
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   pip install -r requirements.txt
   ```

3. **Set Environment Variables**
   Create a `.env` file or export the following environment variables:
   ```bash
   PAPERLESS_URL=<your-paperless-url>
   PAPERLESS_API_TOKEN=<your-paperless-api-token>
   OPENAI_API_KEY=<your-openai-api-key>
   ```

## Usage

### Process a Single Document
Run the `post.py` script with the document ID:
```bash
python src/post.py <document_id>
```

### Process All Documents
Run the `postprocess_all.py` script to process all documents without a specific tag:
```bash
python src/postprocess_all.py
```

### Clean Up Correspondents
Run the `cleanup_correspondents.py` script to clean up correspondents with JSON names:
```bash
python src/cleanup_correspondents.py
```

### Merge Duplicate Correspondents
Run the `merge_duplicates.py` script to merge duplicate correspondents:
```bash
python src/merge_duplicates.py
```

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for details.
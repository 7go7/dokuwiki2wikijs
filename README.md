# DokuWiki to Wiki.js Converter

A Python script that converts DokuWiki pages and media into Markdown files compatible with Wiki.js. This script preserves the namespace structure, links, images, and text formatting, making it easy to import content into Wiki.js.

## Features

- **Converts DokuWiki pages** into Markdown format, with the proper headings, links, images, code blocks, bold/italic formatting, and tables.
- **Preserves the DokuWiki namespace** hierarchy, converting `foo:bar:baz` into `foo/bar/baz.md`.
- **Copies media files** from DokuWiki’s `data/media` directory into an `_media` folder next to the Markdown pages.
- **No external dependencies** required, though the script can utilize `dokuwiki2markdown` if installed for more robust conversion.

## Installation

You can use this script without any installation steps, as long as you have Python 3.8+ installed.

1. Clone the repository:
   ```bash
   git clone https://github.com/7go7/dokuwiki2wikijs.git
   cd <REPO>
````

2. (Optional) Install `dokuwiki2markdown` for enhanced conversions:

   ```bash
   pip install dokuwiki2markdown
   ```

## Usage

Run the script as follows:

```bash
python dokuwiki2wikijs.py /path/to/dokuwiki/data/pages /path/to/output/folder --media-dir /path/to/dokuwiki/data/media --verbose
```

### Arguments:

* `pages_dir`: Path to the `data/pages` directory of your DokuWiki installation.
* `output_dir`: Path to the output directory where Markdown files will be stored.
* `--media-dir`: Path to the `data/media` directory for copying media files (optional).
* `--force`: Overwrite existing files in the output directory.
* `--verbose`: Show detailed output of the conversion process.

## How to Import to Wiki.js

1. Log in to **Wiki.js** as an administrator.
2. Go to **Administration → Import → Markdown Folder**.
3. Select the folder where the converted Markdown files were saved.
4. Review the preview and click **Import**.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributions

Feel free to fork the repo, submit issues, or send pull requests! All contributions are welcome.

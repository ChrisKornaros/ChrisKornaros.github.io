#!/bin/bash
# Imports recipes from ~/Downloads/Recipes into source/pages/recipes/
# - .docx files are converted to .qmd using quarto pandoc
# - .pdf files are copied as-is; a .qmd wrapper is created to embed them
# - Folder structure under ~/Downloads/Recipes is preserved
#
# Run from anywhere. Verify quarto is available first: quarto --version

SRC="$HOME/Downloads/Recipes"
DEST="$(cd "$(dirname "$0")" && pwd)"  # Resolves to source/pages/recipes/
AUTHOR="Chris Kornaros"
DATE=$(date +%Y-%m-%d)

if [[ ! -d "$SRC" ]]; then
    echo "ERROR: Source directory not found: $SRC"
    echo "Make sure your downloaded Recipes folder is at ~/Downloads/Recipes"
    exit 1
fi

echo "Source:      $SRC"
echo "Destination: $DEST"
echo ""

find "$SRC" -type f | sort | while IFS= read -r f; do
    rel="${f#$SRC/}"           # e.g. "Baking/Chocolate Cake.docx"
    dir=$(dirname "$rel")      # e.g. "Baking"
    base=$(basename "$f")      # e.g. "Chocolate Cake.docx"
    ext="${base##*.}"
    name="${base%.*}"          # e.g. "Chocolate Cake"
    category=$(echo "$dir" | cut -d'/' -f1)  # top-level subfolder = category

    # Skip files sitting directly in the root of the Recipes folder (e.g. ebook.pdf)
    if [[ "$dir" == "." ]]; then
        echo "Skipping root-level file: $base"
        continue
    fi

    dest_dir="$DEST/$dir"
    mkdir -p "$dest_dir"

    if [[ "$ext" == "docx" ]]; then
        title="$name"
        output="$dest_dir/$name.qmd"

        echo "Converting: $rel"

        printf '%s\n' \
            '---' \
            "title: \"$title\"" \
            "author: \"$AUTHOR\"" \
            "date: $DATE" \
            "categories: [\"$category\"]" \
            '---' \
            '' > "$output"

        quarto pandoc "$f" --from docx --to markdown >> "$output"

    elif [[ "$ext" == "pdf" ]]; then
        cp "$f" "$dest_dir/$base"

        title="$name"
        output="$dest_dir/$name.qmd"

        echo "Wrapping PDF: $rel"

        printf '%s\n' \
            '---' \
            "title: \"$title\"" \
            "author: \"$AUTHOR\"" \
            "date: $DATE" \
            "categories: [\"$category\"]" \
            '---' \
            '' \
            '```{=html}' \
            "<iframe src=\"$base\" width=\"100%\" height=\"900px\" style=\"border: none;\"></iframe>" \
            '```' > "$output"

    else
        echo "Skipping:   $rel (unsupported type .$ext)"
    fi
done

echo ""
echo "Done. Run 'quarto preview' from source/ to check the results."

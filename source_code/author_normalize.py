import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Values indicating a missing author
MISSING = {"", "(none)", "none", "null", "n/a"}

def clean_name(name):
    # Remove extra spaces
    return re.sub(r"\s+", " ", name).strip()

def author_key(name):
    # Treat different capitalizations as the same author
    return clean_name(name).casefold()

def preferred_name(variants):
    # Select the best capitalization for each author
    def ranking(item):
        name, count = item
        good_case = (
            any(c.islower() for c in name)
            and any(c.isupper() for c in name)
        )
        return (-int(good_case), -count, name.casefold(), name)

    best = sorted(variants.items(), key=ranking)[0][0]

    if best.isupper() or best.islower():
        return best.title()

    return best

def main(input_path):
    input_path = Path(input_path)

    # Store unique authors and their name variations
    variants = defaultdict(Counter)
    source_to_key = {}

    books_read = 0
    books_missing_authors = 0

    # Step 1: Read original books CSV
    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None or "Author" not in reader.fieldnames:
            raise ValueError("Input must have an 'Author' column")

        for book in reader:
            books_read += 1
            has_author = False

            # Step 2: Split multiple authors separated by commas
            for token in (book["Author"] or "").split(","):
                raw = token.strip()
                name = clean_name(raw)
                key = author_key(name)

                if key in MISSING:
                    continue

                has_author = True

                # Step 3: Record each unique author
                variants[key][name] += 1
                source_to_key[raw] = key

            if not has_author:
                books_missing_authors += 1

    # Step 4: Assign unique IDs alphabetically, starting at 1
    keys = sorted(variants)

    key_to_id = {
        key: i
        for i, key in enumerate(keys, start=1)
    }

    out_dir = input_path.parent

    # Step 5: Generate authors.csv
    with (out_dir / "authors.csv").open(
        "w", encoding="utf-8", newline=""
    ) as f:
        writer = csv.writer(f)

        for key in keys:
            writer.writerow([
                key_to_id[key],
                preferred_name(variants[key])
            ])

    # Step 6: Generate author_lookup.csv for teammates
    with (out_dir / "author_lookup.csv").open(
        "w", encoding="utf-8", newline=""
    ) as f:
        writer = csv.writer(f)
        writer.writerow(["source_author", "author_id"])

        for raw in sorted(
            source_to_key,
            key=lambda s: (s.casefold(), s)
        ):
            writer.writerow([
                raw,
                key_to_id[source_to_key[raw]]
            ])

    # Step 7: Print results
    print(f"Books scanned: {books_read:,}")
    print(f"Unique authors: {len(keys):,}")
    print(f"Books without an author: {books_missing_authors:,}")
    print("Generated authors.csv")
    print("Generated author_lookup.csv")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python3 normalize_authors.py books.csv")

    main(sys.argv[1])
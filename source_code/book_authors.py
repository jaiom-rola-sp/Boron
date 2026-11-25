#MXM230183 Manisha
import csv
import re

MISSING = {"", "(none)", "none", "null", "n/a"}

def clean_name(name):
    return re.sub(r"\s+", " ", name).strip()

# lowercase so different capitalizations match, same as the authors script
def author_key(name):
    return clean_name(name).casefold()

rows = []
keys = set()

with open("books_original.csv", "r", encoding="utf-8-sig", newline="") as f:
    for book in csv.DictReader(f):
        isbn = book["ISBN10"].strip()
        title = " ".join(book["Title"].split())
        rows.append((isbn, title, book["Author"] or ""))

        for token in (book["Author"] or "").split(","):
            k = author_key(token)
            if k not in MISSING:
                keys.add(k)

# author ids are alphabetical starting at 1, matches authors.csv
key_to_id = {k: i for i, k in enumerate(sorted(keys), start=1)}

seen_isbns = set()
links = []
seen_links = set()

for isbn, title, authors in rows:
    # skip the same books that books.csv skips
    if not isbn or not title or isbn in seen_isbns:
        continue
    seen_isbns.add(isbn)

    # one row per book and author pair
    for token in authors.split(","):
        k = author_key(token)
        if k in MISSING:
            continue

        pair = (isbn, key_to_id[k])
        if pair not in seen_links:
            seen_links.add(pair)
            links.append(pair)

with open("book_authors.csv", "w", encoding="utf-8", newline="") as f:
    csv.writer(f).writerows(links)

print(f"Books: {len(seen_isbns):,}")
print(f"Authors: {len(key_to_id):,}")
print(f"Links written: {len(links):,}")

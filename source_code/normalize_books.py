#LXK210022 Lyn Kanaan
import csv

# formatting titles while perserving roman numerals and abbreviations
def format_title(title): 
    if not (title.isupper() or title.islower()):
        return title

    formatted_word = []
    roman_num = ("II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII")

    for word in title.split():
        beginning = ""

        while word and word[0] in '([{"':
            beginning += word[0]
            word = word[1:]

        has_num = False

        for character in word:
            if character.isdigit():
                has_num = True
                break

        if has_num or word.count(".") > 1 or word in roman_num:
            new_word = word
        else:
            new_word = word.capitalize()

        formatted_word.append(beginning + new_word)

    return " ".join(formatted_word)   

count = 0
duplicates = 0
missing = 0
total_read = 0
seen_isbns = set()
capital_count = 0
title_exmpl = []

# Open the original books csv file
with open("books_original.csv", "r", encoding="utf-8-sig", newline="") as file:
    reader = csv.DictReader(file)

    # Create a new books file to add the normalization
    with open("books.csv", "w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)

        for row in reader:

            total_read += 1

            # Get 10 digit ISBN and title while removing extra spaces
            isbn = row["ISBN10"].strip()
            title = " ".join(row["Title"].split())

            # Skip records with missing ISBNs or titles
            if not isbn or not title:
                missing += 1
                continue

            # Skip duplicate ISBNs
            if isbn in seen_isbns:
                duplicates += 1
                continue
            else:
                seen_isbns.add(isbn)

            new_title = format_title(title)

            if new_title != title:
                capital_count += 1

                if len(title_exmpl) < 5:
                    title_exmpl.append((title, new_title))

            # Write the ISBN and formatted title to the new books csv
            writer.writerow([isbn, new_title])
            count += 1

# Displaying the results
print("Book normalization complete!")
print(f"Total # of books processed: {count}")
print(f"# of duplicate ISBNs found: {duplicates}")
print(f"# of records with missing data: {missing}")
print(f"# of unique ISBNs found: {len(seen_isbns)}")

print(f"Total # of books read: {total_read}")
print(f"Total # of books written: {count}")
print(f"# of titles reformatted: {capital_count}")

# Display examples of reformatted titles
for original, new in title_exmpl:
    print(f"{original} -> {new}")


import csv

# Open the original borrowers file
with open("borrowers_original.csv", "r", newline="", encoding="utf-8-sig") as infile:
    reader = csv.DictReader(infile)

    # Create the normalized borrowers file
    with open("borrowers.csv", "w", newline="", encoding="utf-8") as outfile:
        writer = csv.writer(outfile)

        # Write the required columns
        writer.writerow(["Card_id", "Ssn", "Bname", "Address", "Phone"])

        # Process each borrower
        for row in reader:
            card_id = row["ID0000id"]
            ssn = row["ssn"]

            # Combine first and last names
            name = row["first_name"].strip() + " " + row["last_name"].strip()

            # Combine address, city, and state
            address = ", ".join([
                row["address"].strip(),
                row["city"].strip(),
                row["state"].strip()
            ])

            phone = row["phone"]

            # Write normalized borrower
            writer.writerow([card_id, ssn, name, address, phone])

print("Borrowers normalization complete!")

# Final validation test
with open("borrowers.csv", "r", newline="", encoding="utf-8") as file:
    reader = csv.DictReader(file)
    rows = list(reader)

    expected_columns = ["Card_id", "Ssn", "Bname", "Address", "Phone"]

    print("\n--- VALIDATION RESULTS ---")
    print("Total borrowers:", len(rows))
    print("Correct columns:", reader.fieldnames == expected_columns)

    card_ids = [row["Card_id"] for row in rows]
    print("Unique Card IDs:", len(set(card_ids)))
    print("No duplicate Card IDs:", len(card_ids) == len(set(card_ids)))

    missing = sum(
        1 for row in rows
        if any(not value.strip() for value in row.values())
    )
    print("Rows with missing information:", missing)

    print("First borrower:", rows[0] if rows else "No records")

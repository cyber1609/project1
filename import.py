import csv
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


def main():
    csvfile = open('books.csv', newline='')
    reader = csv.reader(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    next(reader)


    for isbn, book_name, author, ed_year in reader:
        db.execute("INSERT INTO books (isbn, book_name, author, ed_year) VALUES (:isbn, :book_name, :author, :ed_year)",
                    {"isbn": isbn, "book_name": book_name, "author": author, "ed_year": ed_year})
    db.commit()

if __name__ == "__main__":
    main()
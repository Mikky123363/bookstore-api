import os
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from fastapi import Depends
from dotenv import load_dotenv

# ---------- Load settings from .env ----------
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./books.db")

# ---------- Database setup ----------
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ---------- Database model (the actual database table) ----------
class BookDB(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    author = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    category = Column(String, nullable=False)
    in_stock = Column(Boolean, default=True)
    published_year = Column(Integer, nullable=True)


Base.metadata.create_all(bind=engine)


# ---------- Pydantic schemas (what valid input/output looks like) ----------
class BookCreate(BaseModel):
    title: str
    author: str
    price: float
    category: str
    in_stock: bool = True
    published_year: Optional[int] = None


class BookUpdate(BaseModel):
    title: str
    author: str
    price: float
    category: str
    in_stock: bool = True
    published_year: Optional[int] = None


class BookPatch(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    in_stock: Optional[bool] = None
    published_year: Optional[int] = None


class BookOut(BaseModel):
    id: int
    title: str
    author: str
    price: float
    category: str
    in_stock: bool
    published_year: Optional[int] = None

    class Config:
        from_attributes = True


# ---------- Dependency: gives each request its own database session ----------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app = FastAPI()


# ---------- POST /books/ ----------
@app.post("/books/", response_model=BookOut)
def create_book(book: BookCreate, db: Session = Depends(get_db)):
    new_book = BookDB(**book.dict())
    db.add(new_book)
    db.commit()
    db.refresh(new_book)
    return new_book


# ---------- GET /books/ (with filters) ----------
@app.get("/books/", response_model=List[BookOut])
def get_books(
    category: Optional[str] = None,
    published_after: Optional[int] = None,
    max_price: Optional[float] = None,
    sort_by: Optional[str] = None,
    limit: int = 10,
    skip: int = 0,
    db: Session = Depends(get_db),
):
    query = db.query(BookDB)

    if category:
        query = query.filter(BookDB.category == category)
    if published_after:
        query = query.filter(BookDB.published_year > published_after)
    if max_price:
        query = query.filter(BookDB.price <= max_price)

    if sort_by and hasattr(BookDB, sort_by):
        query = query.order_by(getattr(BookDB, sort_by))

    return query.offset(skip).limit(limit).all()


# ---------- GET /books/{book_id} ----------
@app.get("/books/{book_id}", response_model=BookOut)
def get_book(book_id: int, db: Session = Depends(get_db)):
    book = db.query(BookDB).filter(BookDB.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


# ---------- GET /categories/ ----------
@app.get("/categories/")
def get_categories(db: Session = Depends(get_db)):
    results = db.query(BookDB.category).distinct().all()
    return [row[0] for row in results]


# ---------- GET /categories/{category} ----------
@app.get("/categories/{category}", response_model=List[BookOut])
def get_books_by_category(category: str, db: Session = Depends(get_db)):
    return db.query(BookDB).filter(BookDB.category == category).all()


# ---------- PUT /books/{book_id} (replace the whole book) ----------
@app.put("/books/{book_id}", response_model=BookOut)
def update_book(book_id: int, book: BookUpdate, db: Session = Depends(get_db)):
    existing = db.query(BookDB).filter(BookDB.id == book_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Book not found")

    for key, value in book.dict().items():
        setattr(existing, key, value)

    db.commit()
    db.refresh(existing)
    return existing


# ---------- PATCH /books/{book_id} (update only given fields) ----------
@app.patch("/books/{book_id}", response_model=BookOut)
def patch_book(book_id: int, book: BookPatch, db: Session = Depends(get_db)):
    existing = db.query(BookDB).filter(BookDB.id == book_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Book not found")

    for key, value in book.dict(exclude_unset=True).items():
        setattr(existing, key, value)

    db.commit()
    db.refresh(existing)
    return existing


# ---------- DELETE /books/{book_id} ----------
@app.delete("/books/{book_id}")
def delete_book(book_id: int, db: Session = Depends(get_db)):
    existing = db.query(BookDB).filter(BookDB.id == book_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Book not found")

    db.delete(existing)
    db.commit()
    return {"message": f"Book {book_id} deleted"}

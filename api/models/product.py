from pydantic import BaseModel, HttpUrl
from typing import Optional


class QRCode(BaseModel):
    url: HttpUrl


class Photo(BaseModel):
    url: HttpUrl
    fileId: int


class Product(BaseModel):
    id: int
    name: str
    description: str
    price: int
    qrCode: QRCode
    photo: Photo
    isFavourite: bool
    isAvailableInShop: bool
    isAvailableInGarden: bool


class ProductResponse(BaseModel):
    result: bool
    data: list[Product]

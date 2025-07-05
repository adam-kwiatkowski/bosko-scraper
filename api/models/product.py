from typing import Optional

from pydantic import BaseModel, HttpUrl


class QRCode(BaseModel):
    url: HttpUrl


class Photo(BaseModel):
    url: HttpUrl
    fileId: int


class BaseProduct(BaseModel):
    id: int
    name: str
    isFavourite: bool


class Product(BaseProduct):
    description: Optional[str]
    price: int
    qrCode: QRCode
    photo: Photo
    isAvailableInShop: bool
    isAvailableInGarden: bool

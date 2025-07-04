from typing import Optional, List

from pydantic import BaseModel, HttpUrl


class FileRef(BaseModel):
    url: HttpUrl
    fileId: int


class NamedEntity(BaseModel):
    id: int
    name: str


class TimeRange(BaseModel):
    openingHours: Optional[str]
    closingHours: Optional[str]


class BusinessHours(BaseModel):
    isOpen: bool
    monday: Optional[TimeRange]
    tuesday: Optional[TimeRange]
    wednesday: Optional[TimeRange]
    thursday: Optional[TimeRange]
    friday: Optional[TimeRange]
    saturday: Optional[TimeRange]
    sunday: Optional[TimeRange]


class Industry(BaseModel):
    id: int
    name: str


class Currency(BaseModel):
    code: str
    symbol: str
    numberToBasic: int


class LoyaltyProgram(BaseModel):
    description: str
    isBasedOnPoints: bool
    isBasedOnRebate: bool
    isBasedOnProduct: bool
    type: str
    isReceiptsScannerEnabled: bool
    hasJoinForm: bool
    isJoined: bool
    hasFilledJoinForm: bool
    points: int
    pointsInPending: int
    pointsForCheckIn: Optional[int]
    prizesCount: int
    prizesCountWhichUserCanAfford: int


class Company(BaseModel):
    id: int
    industry: Industry
    logo: FileRef
    cover: Optional[dict]
    name: str
    subdomain: str
    description: str
    address: str
    longitude: float
    latitude: float
    isTapOnPaymentEnabled: bool
    isTapOnPaymentViaMobileDeviceEnabled: bool
    isCorrectionEnabled: bool
    isCorrectionAvailableInAnyOfShops: bool
    gracePeriodInHours: int
    country: NamedEntity
    region: NamedEntity
    city: NamedEntity
    currency: Currency
    loyaltyProgram: LoyaltyProgram
    spentMoney: int
    spentMoneyInPending: int
    deposit: int


class FacebookSocial(BaseModel):
    maximalDistanceForCheckIn: Optional[str]


class Social(BaseModel):
    facebook: Optional[FacebookSocial]
    isCheckInPossible: bool
    pointsCollectedInLastHour: Optional[int]


class Shop(BaseModel):
    id: int
    name: str
    description: str
    rating: float
    telephone: Optional[str]
    address: str
    longitude: float
    latitude: float
    checkInsCount: int
    photo: FileRef
    businessHours: Optional[BusinessHours]
    country: NamedEntity
    region: NamedEntity
    city: NamedEntity
    company: Company
    social: Optional[Social]
    hasGarden: bool
    garden: Optional[dict]
    availableFavouriteProducts: List[dict]
    isFavourite: bool


class ShopResponse(BaseModel):
    result: bool
    data: List[Shop]

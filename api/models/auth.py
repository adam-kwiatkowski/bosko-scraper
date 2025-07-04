from pydantic import BaseModel


class AuthResponse(BaseModel):
    result: bool
    data: str

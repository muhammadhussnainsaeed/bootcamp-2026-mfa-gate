from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str

class VerifyRequest(BaseModel):
    user_id: int
    token: str
    token_type : str

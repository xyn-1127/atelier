from datetime import datetime

from typing import Optional

from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
                                                                                                                                    
from app.db.base import Base
                                                                                                                                    
                
class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id"))
    role: Mapped[str] = mapped_column(String(20))                                                                                  
    content: Mapped[str] = mapped_column(Text)
    reasoning_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="done", server_default="done")
    agent_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tool_calls_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())                                              
                                                                                                                                    
    chat = relationship("Chat", back_populates="messages")
                                                                    
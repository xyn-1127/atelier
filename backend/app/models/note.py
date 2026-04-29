from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, func                                                                    
from sqlalchemy.orm import Mapped, mapped_column, relationship
                                                                                                                                    
from app.db.base import Base


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)                                                                              
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"))
    title: Mapped[str] = mapped_column(String(255))                                                                                
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())                                              
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
                                                                                                                                    
    workspace = relationship("Workspace", back_populates="notes")
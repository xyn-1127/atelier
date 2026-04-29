from datetime import datetime
                                                                                                                                    
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship                                                                     
                
from app.db.base import Base


class File(Base):
    __tablename__ = "files"
                                                                                                                                    
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"))                                                         
    filename: Mapped[str] = mapped_column(String(255))
    filepath: Mapped[str] = mapped_column(Text)                                                                                    
    file_type: Mapped[str] = mapped_column(String(50), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)                                                                    
    status: Mapped[str] = mapped_column(String(20), default="pending")                                                             
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())                         
                                                                                                                                    
    workspace = relationship("Workspace", back_populates="files")
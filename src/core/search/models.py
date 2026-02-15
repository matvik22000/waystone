from dataclasses import asdict, dataclass
from typing import Dict


@dataclass
class SearchDocument:
    """Документ для индексации в поисковой системе"""

    url: str
    text: str
    owner: str
    address: str
    nodeName: str | None

    def to_dict(self) -> Dict:
        """Конвертирует документ в словарь для индексации"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "SearchDocument":
        """Создает документ из словаря"""
        return cls(**data)


@dataclass
class SearchResult:
    """Результат поиска с подсветкой и релевантностью"""

    url: str
    text: str
    owner: str
    address: str
    name: str
    score: float

    # highlighted_text: Optional[str] = None
    # highlighted_node_name: Optional[str] = None

    def to_dict(self) -> Dict:
        """Конвертирует результат в словарь"""
        result = asdict(self)
        # Убираем None значения для чистоты
        return {k: v for k, v in result.items() if v is not None}

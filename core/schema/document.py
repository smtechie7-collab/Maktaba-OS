from typing import List, Optional, Union, Any, Literal
from pydantic import BaseModel, Field


class BaseNode(BaseModel):
    """
    The foundational class for all document nodes.
    Every node in the Maktaba-OS document hierarchy must extend this.
    """
    type: str


class ParagraphNode(BaseNode):
    type: Literal["paragraph"] = "paragraph"
    text: str


class InterlinearToken(BaseModel):
    """
    Represents a single word/morpheme bundle in a linguistic glossing structure.
    Strict vertical alignment is maintained by grouping these fields.
    """
    source_l1: str = Field(..., description="Dominant font, e.g., Arabic/Urdu (<bdi> wrapped)")
    transliteration_l2: str = Field(..., description="Linked via Analysis pointer")
    translation_l3: str = Field(..., description="Linked via Gloss pointer")


class InterlinearBlock(BaseNode):
    """
    A block node that encapsulates an entire interlinear text sequence.
    """
    type: Literal["interlinear_block"] = "interlinear_block"
    tokens: List[InterlinearToken] = Field(default_factory=list)


class FootnoteNode(BaseNode):
    type: Literal["footnote"] = "footnote"
    content: str


class MultilingualBlock(BaseNode):
    """A multilingual paragraph/footnote block for UI persistence."""
    type: Literal["multilingual_block"] = "multilingual_block"
    block_type: Literal["paragraph", "footnote"] = "paragraph"
    ar: Optional[str] = Field(default="", description="Arabic text field")
    ur: Optional[str] = Field(default="", description="Urdu text field")
    gu: Optional[str] = Field(default="", description="Gujarati text field")
    en: Optional[str] = Field(default="", description="English text field")


class MathBlock(BaseNode):
    """
    Handles raw LaTeX syntax and caches the rendered SVG for the Academic demographic.
    """
    type: Literal["math_block"] = "math_block"
    latex_syntax: str
    rendered_svg: Optional[str] = Field(default=None, description="Cached binary/base64 SVG")


class CanvasBlock(BaseNode):
    """
    Interactive Offscreen Canvas node for Children's Book illustrations and Kid Mode.
    """
    type: Literal["canvas_block"] = "canvas_block"
    vector_data: List[Any] = Field(default_factory=list, description="Array of coordinate paths")
    image_overlay: Optional[str] = Field(default=None, description="base64 image payload")


# A tagged union defining all acceptable children nodes for a chapter
BlockNode = frozenset((
    ParagraphNode,
    InterlinearBlock,
    FootnoteNode,
    MathBlock,
    CanvasBlock
))


class ChapterNode(BaseNode):
    type: Literal["chapter"] = "chapter"
    title: str
    children: List[Union[ParagraphNode, InterlinearBlock, FootnoteNode, MathBlock, CanvasBlock, MultilingualBlock]] = Field(default_factory=list)


class DocumentRoot(BaseNode):
    """The absolute root of the Maktaba-OS manuscript."""
    type: Literal["document"] = "document"
    children: List[ChapterNode] = Field(default_factory=list)
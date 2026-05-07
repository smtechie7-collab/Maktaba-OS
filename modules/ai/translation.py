"""
Translation and Localization AI for Maktaba-OS.

This module provides:
- Neural machine translation agent support
- Translation memory and TMX import/export
- Terminology management for consistent multilingual output
- Localization-aware prompt generation
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import logging
import xml.etree.ElementTree as ET
import os
from difflib import SequenceMatcher

from .agent import AIAgent, AgentConfig, AgentContext, AgentResponse, AgentCapability
from .service import AIService, ServiceRequest
from .metrics import metrics_aggregator
from .embeddings import SENTENCE_TRANSFORMERS_AVAILABLE, get_semantic_search_engine

logger = logging.getLogger(__name__)


@dataclass
class TerminologyEntry:
    source_term: str
    target_term: str
    source_language: str
    target_language: str
    domain: str = "general"
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TranslationSegment:
    source_text: str
    translated_text: str
    source_language: str
    target_language: str
    domain: str = "general"
    metadata: Dict[str, Any] = field(default_factory=dict)


class TerminologyManager:
    """Manage a glossary of translation terms and approved terminology."""

    def __init__(self):
        self.entries: List[TerminologyEntry] = []

    def add_entry(self, entry: TerminologyEntry) -> None:
        self.entries.append(entry)
        logger.debug(f"Added terminology entry: {entry.source_term} -> {entry.target_term}")

    def find(self, term: str, source_language: str, target_language: str) -> Optional[TerminologyEntry]:
        for entry in self.entries:
            if (entry.source_term.lower() == term.lower() and
                entry.source_language == source_language and
                entry.target_language == target_language):
                return entry
        return None

    def suggest(self, term: str, source_language: str, target_language: str) -> List[TerminologyEntry]:
        matches = []
        for entry in self.entries:
            if (entry.source_language == source_language and
                entry.target_language == target_language):
                ratio = SequenceMatcher(None, term.lower(), entry.source_term.lower()).ratio()
                if ratio >= 0.65:
                    matches.append(entry)
        return sorted(matches, key=lambda e: SequenceMatcher(None, term.lower(), e.source_term.lower()).ratio(), reverse=True)

    def export_tmx(self, filepath: str) -> None:
        root = ET.Element("tmx", version="1.4")
        body = ET.SubElement(root, "body")
        for entry in self.entries:
            tu = ET.SubElement(body, "tu")
            tuv_source = ET.SubElement(tu, "tuv", attrib={"xml:lang": entry.source_language})
            ET.SubElement(tuv_source, "seg").text = entry.source_term
            tuv_target = ET.SubElement(tu, "tuv", attrib={"xml:lang": entry.target_language})
            ET.SubElement(tuv_target, "seg").text = entry.target_term
        tree = ET.ElementTree(root)
        tree.write(filepath, encoding="utf-8", xml_declaration=True)
        logger.info(f"Exported terminology TMX to {filepath}")

    def import_tmx(self, filepath: str) -> None:
        tree = ET.parse(filepath)
        root = tree.getroot()
        for tuv in root.findall(".//tuv"):
            lang = tuv.attrib.get("{http://www.w3.org/XML/1998/namespace}lang", tuv.attrib.get("xml:lang", ""))
            seg = tuv.find("seg")
            if seg is not None and seg.text:
                self.entries.append(TerminologyEntry(
                    source_term=seg.text,
                    target_term=seg.text,
                    source_language=lang,
                    target_language=lang,
                    domain="general"
                ))
        logger.info(f"Imported terminology TMX from {filepath}")


class TranslationMemory:
    """Store and search translation segments as a reusable memory."""

    def __init__(self):
        self.segments: List[TranslationSegment] = []

    def add_segment(self, segment: TranslationSegment) -> None:
        self.segments.append(segment)
        logger.debug(f"Added translation memory segment: {segment.source_text[:40]}...")

    def search(self, source_text: str, source_language: str, target_language: str, threshold: float = 0.6) -> List[TranslationSegment]:
        if SENTENCE_TRANSFORMERS_AVAILABLE and get_semantic_search_engine():
            engine = get_semantic_search_engine()
            matches = []
            for segment in self.segments:
                if segment.source_language == source_language and segment.target_language == target_language:
                    score = self._semantic_similarity(source_text, segment.source_text)
                    if score >= threshold:
                        matches.append((score, segment))
            matches.sort(key=lambda item: item[0], reverse=True)
            return [segment for _, segment in matches]

        results = []
        for segment in self.segments:
            if segment.source_language != source_language or segment.target_language != target_language:
                continue
            ratio = SequenceMatcher(None, source_text.lower(), segment.source_text.lower()).ratio()
            if ratio >= threshold:
                results.append((ratio, segment))
        results.sort(key=lambda item: item[0], reverse=True)
        return [segment for _, segment in results]

    def _semantic_similarity(self, a: str, b: str) -> float:
        if not SENTENCE_TRANSFORMERS_AVAILABLE or not get_semantic_search_engine():
            return 0.0
        engine = get_semantic_search_engine()
        query_embedding = engine.embedding_model.encode(a)
        target_embedding = engine.embedding_model.encode(b)
        from numpy import dot
        from numpy.linalg import norm
        if norm(query_embedding) == 0 or norm(target_embedding) == 0:
            return 0.0
        return float(dot(query_embedding[0], target_embedding[0]) / (norm(query_embedding[0]) * norm(target_embedding[0])))

    def export_tmx(self, filepath: str) -> None:
        root = ET.Element("tmx", version="1.4")
        body = ET.SubElement(root, "body")
        for seg in self.segments:
            tu = ET.SubElement(body, "tu")
            tuv_source = ET.SubElement(tu, "tuv", attrib={"xml:lang": seg.source_language})
            ET.SubElement(tuv_source, "seg").text = seg.source_text
            tuv_target = ET.SubElement(tu, "tuv", attrib={"xml:lang": seg.target_language})
            ET.SubElement(tuv_target, "seg").text = seg.translated_text
        tree = ET.ElementTree(root)
        tree.write(filepath, encoding="utf-8", xml_declaration=True)
        logger.info(f"Exported translation memory TMX to {filepath}")

    def import_tmx(self, filepath: str) -> None:
        tree = ET.parse(filepath)
        root = tree.getroot()
        pairs = []
        for tu in root.findall(".//tu"):
            source_text = ""
            translated_text = ""
            source_language = ""
            target_language = ""
            for tuv in tu.findall("tuv"):
                lang = tuv.attrib.get("{http://www.w3.org/XML/1998/namespace}lang", tuv.attrib.get("xml:lang", ""))
                seg = tuv.find("seg")
                if seg is None or seg.text is None:
                    continue
                if not source_text:
                    source_text = seg.text
                    source_language = lang
                else:
                    translated_text = seg.text
                    target_language = lang
            if source_text and translated_text:
                self.add_segment(TranslationSegment(
                    source_text=source_text,
                    translated_text=translated_text,
                    source_language=source_language,
                    target_language=target_language
                ))
        logger.info(f"Imported translation memory TMX from {filepath}")


class TranslationAgent(AIAgent):
    """AI agent for translation and localization tasks."""

    def __init__(self, config: AgentConfig, ai_service: AIService):
        super().__init__(config)
        self.ai_service = ai_service
        self.metrics = metrics_aggregator.register_agent(f"translation_{config.name}")
        self.terminology = TerminologyManager()
        self.memory = TranslationMemory()

    async def _validate_config(self) -> None:
        if AgentCapability.TRANSLATION not in self.config.capabilities:
            raise ValueError("TranslationAgent requires TRANSLATION capability")
        if not self.ai_service:
            raise ValueError("AI service is required for TranslationAgent")

    async def _initialize_models(self) -> None:
        healthy = await self.ai_service.check_health()
        if not healthy:
            raise RuntimeError(f"AI service is not healthy: {self.config.model_provider}")

    async def _setup_monitoring(self) -> None:
        logger.info(f"TranslationAgent {self.name} monitoring enabled")

    async def process(self, input_data: Dict[str, Any], context: AgentContext) -> AgentResponse:
        start_time = __import__('time').time()
        task_type = input_data.get("task_type", "translate")
        source_text = input_data.get("content", "")
        source_language = input_data.get("source_language", "en")
        target_language = input_data.get("target_language", "ar")
        domain = input_data.get("domain", "general")
        locale = input_data.get("locale", "standard")

        try:
            if task_type == "translate":
                translated = await self._translate(source_text, source_language, target_language, domain, locale)
                result = translated
            elif task_type == "localize":
                result = await self._localize(source_text, source_language, target_language, domain, locale)
            elif task_type == "glossary":
                term = input_data.get("term", "")
                result = self._lookup_glossary(term, source_language, target_language)
            elif task_type == "memory_search":
                result = self._search_memory(source_text, source_language, target_language)
            else:
                result = await self._translate(source_text, source_language, target_language, domain, locale)

            response_time = __import__('time').time() - start_time
            self.metrics.record_request(success=True, input_tokens=len(source_text) // 4, response_time=response_time)

            return AgentResponse(
                content=result,
                metadata={
                    "task_type": task_type,
                    "source_language": source_language,
                    "target_language": target_language,
                    "locale": locale,
                    "domain": domain
                },
                tokens_used=len(source_text) // 4,
                processing_time=response_time,
                model_used=self.config.model_name
            )

        except Exception as e:
            logger.error(f"TranslationAgent failed: {e}")
            response_time = __import__('time').time() - start_time
            self.metrics.record_request(success=False, input_tokens=len(source_text) // 4, response_time=response_time)
            return AgentResponse(content="", error_message=str(e), processing_time=response_time)

    async def _translate(self, source_text: str, source_language: str, target_language: str, domain: str, locale: str) -> str:
        memory_matches = self.memory.search(source_text, source_language, target_language)
        glossary = self._build_glossary_hint(source_text, source_language, target_language)
        prompt = self._build_translation_prompt(source_text, source_language, target_language, domain, locale, glossary, memory_matches)

        request = ServiceRequest(
            model=self.config.model_name,
            messages=[
                {"role": "system", "content": self._get_system_instruction(source_language, target_language, locale, domain)},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=min(self.config.max_tokens, 1600)
        )
        response = await self.ai_service.generate_text(request)
        return response.content

    async def _localize(self, source_text: str, source_language: str, target_language: str, domain: str, locale: str) -> str:
        glossary = self._build_glossary_hint(source_text, source_language, target_language)
        prompt = (
            f"Translate and adapt the following text for {locale} readers. Preserve meaning, cultural context, and appropriate tone."
            f" Use the approved terminology when possible.\n\nSource text:\n{source_text}"
        )
        if glossary:
            prompt += f"\n\nUse these glossary entries:\n{glossary}"

        request = ServiceRequest(
            model=self.config.model_name,
            messages=[
                {"role": "system", "content": self._get_system_instruction(source_language, target_language, locale, domain, localize=True)},
                {"role": "user", "content": prompt}
            ],
            temperature=0.25,
            max_tokens=min(self.config.max_tokens, 1600)
        )
        response = await self.ai_service.generate_text(request)
        return response.content

    def _build_translation_prompt(
        self,
        source_text: str,
        source_language: str,
        target_language: str,
        domain: str,
        locale: str,
        glossary_hint: str,
        memory_matches: List[TranslationSegment]
    ) -> str:
        prompt = (
            f"Translate the following text from {source_language} to {target_language}."
            f" Use a tone appropriate for {locale} readers and preserve domain-specific terminology.\n\n"
            f"Source text:\n{source_text}"
        )
        if glossary_hint:
            prompt += f"\n\nUse these terminology entries:\n{glossary_hint}"
        if memory_matches:
            prompt += "\n\nPrevious translation memory matches for reference:\n"
            for idx, match in enumerate(memory_matches[:3], 1):
                prompt += f"{idx}. {match.source_text} -> {match.translated_text}\n"
        return prompt

    def _get_system_instruction(self, source_language: str, target_language: str, locale: str, domain: str, localize: bool = False) -> str:
        instruction = (
            f"You are a translation specialist. Translate text from {source_language} to {target_language} accurately."
            f" Maintain cultural sensitivity for {locale} readers and preserve the domain specificity of {domain}."
        )
        if localize:
            instruction += " Prioritize natural localization and idiomatic phrasing over literal translation."
        return instruction

    def _build_glossary_hint(self, source_text: str, source_language: str, target_language: str) -> str:
        terms = []
        for entry in self.terminology.entries:
            if entry.source_language == source_language and entry.target_language == target_language:
                if entry.source_term.lower() in source_text.lower():
                    terms.append(f"{entry.source_term} -> {entry.target_term}")
        return "\n".join(terms)

    def _lookup_glossary(self, term: str, source_language: str, target_language: str) -> str:
        entry = self.terminology.find(term, source_language, target_language)
        if entry:
            return f"{entry.source_term} -> {entry.target_term} ({entry.domain})"
        suggestions = self.terminology.suggest(term, source_language, target_language)
        if not suggestions:
            return "No glossary entry found."
        return "Suggested entries:\n" + "\n".join(f"{s.source_term} -> {s.target_term}" for s in suggestions)

    def _search_memory(self, source_text: str, source_language: str, target_language: str) -> str:
        matches = self.memory.search(source_text, source_language, target_language)
        if not matches:
            return "No matching translation memory entries found."
        return "\n".join(f"{m.source_text} -> {m.translated_text} (domain={m.domain})" for m in matches[:5])


def create_translation_agent(
    name: str = "translator",
    model_provider: Any = None,
    model_name: str = "gpt-4",
    api_key: Optional[str] = None
) -> TranslationAgent:
    from .service import AIServiceConfig, OpenAIService, ModelProvider as ProviderEnum

    provider = model_provider or ProviderEnum.OPENAI
    if not isinstance(provider, ProviderEnum):
        provider = ProviderEnum(provider)

    service_config = AIServiceConfig(
        provider=provider,
        api_key=api_key
    )

    if provider == ProviderEnum.OPENAI:
        ai_service = OpenAIService(service_config)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    agent_config = AgentConfig(
        name=name,
        description="AI translation and localization agent",
        capabilities=[AgentCapability.TRANSLATION],
        model_provider=provider.value,
        model_name=model_name,
        temperature=0.3,
        max_tokens=1600
    )

    return TranslationAgent(agent_config, ai_service)

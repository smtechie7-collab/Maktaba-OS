"""
Content Intelligence and Writing Assistance for Maktaba-OS.

This module provides advanced content intelligence features including:
- Intelligent content suggestions and auto-complete
- Content quality scoring and improvement recommendations
- Style consistency analysis across multilingual content
- Plagiarism detection and citation assistance
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
import logging
import re
import math

from .agent import AIAgent, AgentConfig, AgentContext, AgentResponse, AgentCapability
from .service import AIService, ServiceRequest
from .metrics import metrics_aggregator
from .embeddings import (
    SENTENCE_TRANSFORMERS_AVAILABLE,
    initialize_semantic_search,
    get_semantic_search_engine,
    SemanticSearchEngine,
)

logger = logging.getLogger(__name__)


@dataclass
class ContentQualityReport:
    score: float
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    readability_grade: Optional[str] = None
    structure_score: Optional[float] = None
    style_score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StyleAnalysisReport:
    consistency_score: float
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    tone: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlagiarismCheckResult:
    similarity_score: float
    matched_snippets: List[Dict[str, Any]] = field(default_factory=list)
    source_references: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ContentIntelligenceAgent(AIAgent):
    """
    AI agent for content intelligence tasks.

    Capabilities:
    - Intelligent content suggestions
    - Auto-completion
    - Automated quality scoring
    - Style analysis
    - Plagiarism detection and citation assistance
    """

    def __init__(self, config: AgentConfig, ai_service: AIService):
        super().__init__(config)
        self.ai_service = ai_service
        self.metrics = metrics_aggregator.register_agent(f"content_intelligence_{config.name}")
        self.semantic_engine = None

        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.semantic_engine = get_semantic_search_engine()
                if self.semantic_engine is None:
                    self.semantic_engine = initialize_semantic_search()
            except Exception as e:
                logger.warning(f"Semantic search engine initialization failed: {e}")
                self.semantic_engine = None

    async def _validate_config(self) -> None:
        if AgentCapability.TEXT_ANALYSIS not in self.config.capabilities:
            raise ValueError("ContentIntelligenceAgent requires TEXT_ANALYSIS capability")

        if not self.ai_service:
            raise ValueError("AI service is required for ContentIntelligenceAgent")

    async def _initialize_models(self) -> None:
        is_healthy = await self.ai_service.check_health()
        if not is_healthy:
            raise RuntimeError(f"AI service is not healthy: {self.config.model_provider}")

    async def _setup_monitoring(self) -> None:
        logger.info(f"ContentIntelligenceAgent {self.name} monitoring enabled")

    async def process(self, input_data: Dict[str, Any], context: AgentContext) -> AgentResponse:
        start_time = __import__('time').time()
        task_type = input_data.get("task_type", "suggestion")
        language = input_data.get("language", context.language)
        style = input_data.get("style", "academic")
        content = input_data.get("content", "")
        topic = input_data.get("topic", "")

        try:
            if task_type in {"suggestion", "autocomplete", "improve", "outline", "expand", "summarize", "rewrite"}:
                response_text = await self._generate_content(task_type, content, topic, language, style, input_data)
                result_content = response_text
            elif task_type in {"footnote", "citation"}:
                response_text = await self._generate_content(task_type, content, topic, language, style, input_data)
                result_content = response_text
            elif task_type in {"collaborate", "brainstorm"}:
                result_content = await self._generate_collaborative_response(task_type, content, topic, language, style, input_data, context)
            elif task_type == "quality":
                report = self._generate_quality_report(content)
                result_content = self._format_quality_report(report)
            elif task_type == "style":
                report = self._generate_style_analysis(content, style)
                result_content = self._format_style_report(report)
            elif task_type == "plagiarism":
                known_texts = input_data.get("known_texts", [])
                report = self._detect_plagiarism(content, known_texts)
                result_content = self._format_plagiarism_report(report)
            else:
                response_text = await self._generate_content("suggestion", content, topic, language, style, input_data)
                result_content = response_text

            response_time = __import__('time').time() - start_time
            self.metrics.record_request(success=True, input_tokens=len(content) // 4, response_time=response_time)

            return AgentResponse(
                content=result_content,
                metadata={"task_type": task_type, "language": language, "style": style},
                tokens_used=len(content) // 4,
                processing_time=response_time,
                model_used=self.config.model_name
            )

        except Exception as e:
            logger.error(f"Content intelligence task failed: {e}")
            response_time = __import__('time').time() - start_time
            self.metrics.record_request(success=False, input_tokens=len(content) // 4, response_time=response_time)
            return AgentResponse(content="", error_message=str(e), processing_time=response_time)

    async def _generate_content(
        self,
        task_type: str,
        content: str,
        topic: str,
        language: str,
        style: str,
        input_data: Dict[str, Any]
    ) -> str:
        prompt = self._build_prompt(task_type, content, topic, language, style, input_data)
        request = ServiceRequest(
            model=self.config.model_name,
            messages=[
                {"role": "system", "content": self._get_system_prompt(language, style, task_type)},
                {"role": "user", "content": prompt}
            ],
            temperature=self._get_temperature(task_type),
            max_tokens=self._get_max_tokens(task_type, input_data)
        )
        response = await self.ai_service.generate_text(request)
        return response.content

    async def _generate_collaborative_response(
        self,
        task_type: str,
        content: str,
        topic: str,
        language: str,
        style: str,
        input_data: Dict[str, Any],
        context: AgentContext
    ) -> str:
        history_items = input_data.get("conversation_history") or context.conversation_history or []
        history_text = self._render_conversation_history(history_items)
        prompt = self._build_prompt(task_type, content, topic, language, style, input_data, history=history_text)

        request = ServiceRequest(
            model=self.config.model_name,
            messages=[
                {"role": "system", "content": self._get_system_prompt(language, style, task_type)},
                {"role": "user", "content": prompt}
            ],
            temperature=self._get_temperature(task_type),
            max_tokens=self._get_max_tokens(task_type, input_data)
        )
        response = await self.ai_service.generate_text(request)
        return response.content

    def _render_conversation_history(self, history_items: List[Dict[str, Any]]) -> str:
        if not history_items:
            return ""
        rendered = []
        for item in history_items:
            role = item.get("role", "user").capitalize()
            text = item.get("content", "")
            rendered.append(f"{role}: {text}")
        return "\n".join(rendered)

    def _build_prompt(
        self,
        task_type: str,
        content: str,
        topic: str,
        language: str,
        style: str,
        input_data: Dict[str, Any],
        history: str = ""
    ) -> str:
        if task_type == "suggestion":
            return (
                f"Review the following content and provide 3 intelligent suggestions for improving structure, tone, and relevance."
                f"\n\nContent:\n{content}\n\nTopic: {topic}\nStyle: {style}\nLanguage: {language}"
            )

        if task_type == "autocomplete":
            return (
                f"Continue and complete the following draft in the same style and language. Return a natural continuation that preserves the original voice."
                f"\n\nDraft:\n{content}\n\nTopic: {topic}\nStyle: {style}\nLanguage: {language}"
            )

        if task_type == "improve":
            return (
                f"Improve the following text by making it more engaging, concise, and aligned with the requested style."
                f"\n\nText:\n{content}\n\nStyle: {style}\nLanguage: {language}"
            )

        if task_type == "outline":
            return (
                f"Create a detailed outline for an article about: {topic}."
                f" Structure it with main sections, subsections, and key points to cover."
                f" Make it suitable for {style} writing in {language}."
            )

        if task_type == "expand":
            return (
                f"Expand the following content while maintaining its style and adding relevant details."
                f"\n\nContent:\n{content}\n\nTopic: {topic}\nStyle: {style}\nLanguage: {language}"
            )

        if task_type == "summarize":
            length = input_data.get("length", "medium")
            return (
                f"Summarize the following content in a {length} format."
                f"\n\nContent:\n{content}\n\nStyle: {style}\nLanguage: {language}"
            )

        if task_type == "rewrite":
            target_style = input_data.get("target_style", style)
            return (
                f"Rewrite the following content in a {target_style} style for a different audience."
                f"\n\nOriginal content:\n{content}\n\nTarget style: {target_style}\nLanguage: {language}"
            )

        if task_type == "quality":
            return (
                f"Analyze the following text for quality, readability, coherence, and relevance. Provide a score from 0 to 1 and three concrete improvement suggestions."
                f"\n\nText:\n{content}"
            )

        if task_type == "style":
            return (
                f"Analyze this text for style consistency, tone, and format. Identify inconsistencies and give three recommendations to improve style alignment."
                f"\n\nText:\n{content}\n\nDesired style: {style}\nLanguage: {language}"
            )

        if task_type == "plagiarism":
            return (
                f"Check the text for potential plagiarism or uncredited similarity to known sources."
                f"\n\nText:\n{content}"
            )

        if task_type == "footnote":
            requested_topic = topic or "the topic of the passage"
            return (
                f"Generate concise academic footnotes for the following passage on the topic: {requested_topic}."
                f" Provide one or two numbered footnotes that clarify key points and cite any conceptual references clearly."
                f"\n\nText:\n{content}"
            )

        if task_type == "citation":
            reference_style = input_data.get("reference_style", "APA")
            source_type = input_data.get("source_type", "source")
            return (
                f"Create a list of {reference_style} formatted citations or references for the key claims in the following text." 
                f" Use {source_type} style references when possible, and if exact sources are unknown, provide scholarly placeholders that fit the topic: {topic}."
                f"\n\nText:\n{content}"
            )

        if task_type in {"collaborate", "brainstorm"}:
            history_section = f"\n\nConversation History:\n{history}" if history else ""
            return (
                f"Act as a collaborative writing assistant for this draft. Review the current content and the conversation history,"
                f" then propose the next step, a stronger paragraph, or an improvement plan."
                f"\n\nDraft:\n{content}\n\nTopic: {topic}\nStyle: {style}\nLanguage: {language}"
                f"{history_section}"
            )

        return content

    def _get_system_prompt(self, language: str, style: str, task_type: str) -> str:
        prompt = (
            f"You are an expert content intelligence assistant for religious, multilingual publications."
            f" Provide accurate, respectful, and domain-aware responses."
            f" Maintain the requested style: {style}."
        )
        if language != "en":
            prompt += f" Respond in {language} only."
        if task_type in {"quality", "style", "plagiarism"}:
            prompt += " Focus on analysis, not generation."
        return prompt

    def _get_temperature(self, task_type: str) -> float:
        values = {
            "suggestion": 0.65,
            "autocomplete": 0.7,
            "improve": 0.6,
            "outline": 0.3,
            "expand": 0.6,
            "summarize": 0.3,
            "rewrite": 0.5,
            "footnote": 0.2,
            "citation": 0.25,
            "collaborate": 0.55,
            "brainstorm": 0.7,
            "quality": 0.25,
            "style": 0.3,
            "plagiarism": 0.2
        }
        return values.get(task_type, 0.5)

    def _get_max_tokens(self, task_type: str, input_data: Dict[str, Any]) -> int:
        if task_type == "autocomplete":
            return min(self.config.max_tokens, input_data.get("max_tokens", 800))
        if task_type in {"suggestion", "improve"}:
            return min(self.config.max_tokens, 600)
        if task_type == "outline":
            return min(self.config.max_tokens, 800)
        if task_type == "expand":
            return min(self.config.max_tokens, 1000)
        if task_type == "summarize":
            return min(self.config.max_tokens, 400)
        if task_type == "rewrite":
            return min(self.config.max_tokens, 800)
        if task_type == "footnote":
            return min(self.config.max_tokens, 300)
        if task_type == "citation":
            return min(self.config.max_tokens, 400)
        if task_type in {"collaborate", "brainstorm"}:
            return min(self.config.max_tokens, 700)
        return min(self.config.max_tokens, 400)

    def _generate_quality_report(self, content: str) -> ContentQualityReport:
        score = self._assess_quality_score(content)
        strengths = []
        weaknesses = []
        recommendations = []

        if score >= 0.8:
            strengths.append("Clear structure and coherent flow")
        if score <= 0.6:
            weaknesses.append("The text may be too verbose or repetitive")
            recommendations.append("Simplify complex sentences and remove duplicate ideas")

        if self._has_passive_voice(content):
            weaknesses.append("Passive voice usage detected")
            recommendations.append("Prefer active voice for stronger engagement")

        readability = self._readability_grade(content)
        if readability and readability not in {"Easy", "Very Easy"}:
            recommendations.append(f"Aim for {readability.lower()} sentence structure")

        if not recommendations:
            recommendations.append("Review the text for clarity and remove unnecessary repetition.")

        return ContentQualityReport(
            score=score,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations,
            readability_grade=readability,
            structure_score=min(1.0, score + 0.05),
            style_score=0.0,
            metadata={"word_count": len(content.split())}
        )

    def _generate_style_analysis(self, content: str, style: str) -> StyleAnalysisReport:
        consistency = self._assess_style_consistency(content, style)
        issues = []
        recommendations = []

        if consistency < 0.6:
            issues.append("Inconsistent tone or formality")
            recommendations.append("Unify sentence structure and maintain a single voice")
        if self._detect_mixed_tenses(content):
            issues.append("Mixed tense usage detected")
            recommendations.append("Use consistent tense across the passage")

        return StyleAnalysisReport(
            consistency_score=consistency,
            issues=issues,
            recommendations=recommendations,
            tone=style,
            metadata={"style": style}
        )

    def _detect_plagiarism(self, content: str, known_texts: Optional[List[Dict[str, Any]]] = None) -> PlagiarismCheckResult:
        matches = []
        score = 0.0
        source_references = []

        if self.semantic_engine and known_texts:
            engine = SemanticSearchEngine(self.semantic_engine.model_name)
            texts = [item.get("content", "") for item in known_texts]
            metadata = [{"source": item.get("source", f"source_{i}")} for i, item in enumerate(known_texts)]
            engine.add_texts(texts, metadata=metadata)
            results = engine.search(content, k=5)
            for result in results:
                if result["score"] >= 0.65:
                    matches.append({
                        "source": result["metadata"].get("source", "unknown"),
                        "text": result["content"],
                        "score": result["score"]
                    })
                    source_references.append(result["metadata"].get("source", "unknown"))
            score = max((r["score"] for r in matches), default=0.0)
        else:
            known_texts = known_texts or []
            text_tokens = set(re.findall(r"\w+", content.lower()))
            for item in known_texts:
                candidate = item.get("content", "")
                candidate_tokens = set(re.findall(r"\w+", candidate.lower()))
                overlap = len(text_tokens.intersection(candidate_tokens))
                if candidate_tokens:
                    similarity = overlap / len(candidate_tokens)
                else:
                    similarity = 0.0
                if similarity >= 0.15:
                    matches.append({
                        "source": item.get("source", "unknown"),
                        "text": candidate,
                        "score": similarity
                    })
                    source_references.append(item.get("source", "unknown"))
            score = max((r["score"] for r in matches), default=0.0)

        return PlagiarismCheckResult(
            similarity_score=round(score, 3),
            matched_snippets=matches,
            source_references=list(dict.fromkeys(source_references)),
            metadata={"checked_sources": len(known_texts)}
        )

    def _format_quality_report(self, report: ContentQualityReport) -> str:
        return (
            f"Quality Score: {report.score:.2f}\n"
            f"Readability: {report.readability_grade or 'Unknown'}\n"
            f"Strengths: {', '.join(report.strengths) or 'None'}\n"
            f"Weaknesses: {', '.join(report.weaknesses) or 'None'}\n"
            f"Recommendations:\n - " + "\n - ".join(report.recommendations or ["No recommendations available."])
        )

    def _format_style_report(self, report: StyleAnalysisReport) -> str:
        return (
            f"Style Consistency Score: {report.consistency_score:.2f}\n"
            f"Tone: {report.tone or 'unspecified'}\n"
            f"Issues: {', '.join(report.issues) or 'None'}\n"
            f"Recommendations:\n - " + "\n - ".join(report.recommendations or ["No recommendations available."])
        )

    def _format_plagiarism_report(self, report: PlagiarismCheckResult) -> str:
        if not report.matched_snippets:
            return "No significant similarity detected. Content appears original based on known sources."
        lines = [f"Plagiarism Similarity Score: {report.similarity_score:.2f}"]
        for match in report.matched_snippets:
            lines.append(f"- Source: {match['source']} (score: {match['score']:.2f})")
        return "\n".join(lines)

    def _assess_quality_score(self, content: str) -> float:
        if not content or len(content.strip()) < 20:
            return 0.0
        word_count = len(content.split())
        score = 0.4
        score += min(0.2, (word_count / 2000))
        sentence_count = max(1, content.count(".") + content.count("?") + content.count("!"))
        avg_sentence = word_count / sentence_count
        if 12 <= avg_sentence <= 22:
            score += 0.2
        if self._has_passive_voice(content):
            score -= 0.1
        if self._find_repetitive_phrases(content):
            score -= 0.1
        return max(0.0, min(1.0, score))

    def _assess_style_consistency(self, content: str, style: str) -> float:
        score = 0.5
        if style.lower() in content.lower():
            score += 0.1
        if self._detect_mixed_tenses(content):
            score -= 0.15
        if self._has_repeated_sentence_patterns(content):
            score -= 0.1
        return max(0.0, min(1.0, score))

    def _readability_grade(self, content: str) -> Optional[str]:
        sentences = re.split(r"[.!?]", content)
        words = re.findall(r"\w+", content)
        if not sentences or not words:
            return None
        avg_words = len(words) / max(1, len(sentences))
        if avg_words <= 12:
            return "Very Easy"
        if avg_words <= 17:
            return "Easy"
        if avg_words <= 22:
            return "Standard"
        return "Difficult"

    def _has_passive_voice(self, content: str) -> bool:
        return bool(re.search(r"\b(is|was|were|been|be|being)\b\s+\w+ed\b", content.lower()))

    def _detect_mixed_tenses(self, content: str) -> bool:
        past = bool(re.search(r"\b(was|were|had|did|said|went)\b", content.lower()))
        present = bool(re.search(r"\b(is|are|has|does|says|goes)\b", content.lower()))
        return past and present

    def _find_repetitive_phrases(self, content: str) -> bool:
        words = re.findall(r"\w+", content.lower())
        return any(words.count(word) > 5 for word in set(words))

    def _has_repeated_sentence_patterns(self, content: str) -> bool:
        sentences = [s.strip() for s in re.split(r"[.!?]", content) if s.strip()]
        return len(set(sentences)) < len(sentences) * 0.8


def create_content_intelligence_agent(
    name: str = "content_intel",
    model_provider: Any = None,
    model_name: str = "gpt-4",
    api_key: Optional[str] = None
) -> ContentIntelligenceAgent:
    from .service import AIServiceConfig, OpenAIService
    from .service import ModelProvider as ProviderEnum

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
        description="AI content intelligence and writing assistance",
        capabilities=[AgentCapability.TEXT_ANALYSIS, AgentCapability.REVIEW],
        model_provider=provider.value,
        model_name=model_name,
        temperature=0.3,
        max_tokens=1200
    )

    return ContentIntelligenceAgent(agent_config, ai_service)

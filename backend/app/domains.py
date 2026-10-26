"""Domain profiles: what the assistant is for. DOMAIN in .env picks one and every agent prompt is built around it.

A restricted domain (healthcare, technology) makes the assistant domain-only:
  planner      turns away requests outside the domain before any search ("out_of_scope" route)
  verifier     checks that the question and every retrieved source belong to the domain; off-domain sources
               are dropped and an off-domain question is declined
  synthesizer  answers as a specialist of the domain, following its answer rules
"general" keeps the assistant open to any topic (no domain gate).

To add a domain, add a Domain(...) entry to DOMAINS.
"""
from dataclasses import dataclass
from functools import lru_cache

from .config import get_settings


@dataclass(frozen=True)
class Domain:
    key: str
    name: str                  # used in prompts and messages: "healthcare"
    title: str                 # UI heading
    role: str                  # who the assistant is: "a healthcare information assistant"
    scope: str                 # what belongs to the domain
    out_of_scope: str          # examples of what doesn't
    topics_hint: str           # short list for the "I can only help with…" reply
    answer_rules: str          # domain-specific rules for the synthesizer
    suggestions: tuple[str, ...]
    restricted: bool = True    # False = any topic is fine

    @property
    def out_of_scope_message(self) -> str:
        return (
            f"I'm a {self.name} assistant, so I can only help with {self.name} questions — for example "
            f"{self.topics_hint}. Feel free to ask me something in that area."
        )


DOMAINS: dict[str, Domain] = {
    "healthcare": Domain(
        key="healthcare",
        name="healthcare",
        title="Healthcare Assistant",
        role="a healthcare information assistant",
        scope=(
            "human health and medicine — diseases and conditions, symptoms, tests and diagnosis, treatments and "
            "procedures, medications (uses, side effects, interactions), mental health, nutrition and exercise as they "
            "relate to health, prevention and vaccines, anatomy and physiology, public health and epidemiology, "
            "healthcare services and providers, health insurance and hospital/clinic processes, medical devices and "
            "health technology, and healthcare policy, research and regulation"
        ),
        out_of_scope=(
            "anything that is not about health or healthcare — e.g. programming, gadgets, sports results, finance and "
            "stock prices, travel, cooking (unless about a medical diet), entertainment, astronomy or general trivia"
        ),
        topics_hint="conditions and symptoms, treatments, medications, prevention, mental health or healthcare services",
        answer_rules=(
            "- Give general health information, not a diagnosis or a personal treatment plan. When the user describes\n"
            "  their own symptoms or asks what they personally should take or do, explain what the sources say and\n"
            "  recommend they talk to a doctor, pharmacist or other qualified professional.\n"
            "- If the message mentions possible emergency signs (chest pain, trouble breathing, signs of stroke, severe\n"
            "  bleeding, loss of consciousness, thoughts of suicide or self-harm), start by telling them to contact local\n"
            "  emergency services or a crisis line right away.\n"
            "- Only give doses, drug interactions, test values or treatment steps that the sources state — never estimate\n"
            "  or fill them in yourself.\n"
            "- Use plain language and briefly explain medical terms."
        ),
        suggestions=(
            "What are the early symptoms of type 2 diabetes?",
            "How does the flu vaccine work?",
            "Summarize the treatment guidelines in my documents",
            "What are common side effects of ibuprofen?",
        ),
    ),
    "technology": Domain(
        key="technology",
        name="technology",
        title="Technology Assistant",
        role="a technology assistant",
        scope=(
            "computing and technology — software development and programming languages, frameworks, libraries and "
            "tools, computer science, AI and machine learning, data and databases, cloud, DevOps and infrastructure, "
            "networking, defensive cybersecurity, operating systems, hardware and electronics, consumer devices and "
            "gadgets, IT operations and support, and the technology industry (products, companies, releases)"
        ),
        out_of_scope=(
            "anything that is not about technology — e.g. medical or health advice, cooking, sports, politics, travel, "
            "entertainment gossip, relationships, or astronomy and other sciences unrelated to technology"
        ),
        topics_hint="programming, software and tools, AI, cloud and infrastructure, cybersecurity, hardware or devices",
        answer_rules=(
            "- Be precise and practical. Put code, commands and config in fenced code blocks with the language.\n"
            "- Mention versions when behaviour differs between versions, and never assume an API, flag or setting exists\n"
            "  unless the sources show it.\n"
            "- Point out security risks in code or configuration and prefer secure defaults.\n"
            "- Prefer official documentation when the sources include it."
        ),
        suggestions=(
            "Explain the difference between REST and GraphQL",
            "What's new in the latest Python release?",
            "Summarize the architecture described in my documents",
            "How do I secure an API with OAuth 2.0?",
        ),
    ),
    "general": Domain(
        key="general",
        name="general",
        title="Research Assistant",
        role="a research assistant",
        scope="any topic",
        out_of_scope="nothing",
        topics_hint="anything in your documents or on the web",
        answer_rules="",
        suggestions=(
            "Summarize the key points of my uploaded documents",
            "What does the refund policy say?",
            "Compare the latest news on this topic with my documents",
            "List any deadlines or dates mentioned in the files",
        ),
        restricted=False,
    ),
}


@lru_cache
def active_domain() -> Domain:
    key = get_settings().domain.strip().lower()
    if key not in DOMAINS:
        raise ValueError(f"Unknown DOMAIN '{key}' in .env. Choose one of: {', '.join(DOMAINS)}")
    return DOMAINS[key]

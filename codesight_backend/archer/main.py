from fastapi import FastAPI
from .models import ArchitectureInput, RecommendationResponse
from .rules import analyze_architecture
from .gigachat_client import GigaChatArchitectureAdvisor
from .promts import build_user_prompt
from .formatter import ModelOutputFormatter


app = FastAPI(title="Architecture Recommendation Agent")

advisor = GigaChatArchitectureAdvisor()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze", response_model=RecommendationResponse)
def analyze(data: ArchitectureInput):
    findings = analyze_architecture(data)

    payload = {
        "project_name": data.project_name,
        "business_context": data.business_context,
        "architecture_summary": data.architecture_summary,
        "services": [svc.model_dump() for svc in data.services],
        "known_issues": data.known_issues,
        "quality_attributes": data.quality_attributes,
    }

    prompt = build_user_prompt(payload, findings)
    llm_output = advisor.recommend(prompt)

    # Форматируем вывод модели
    formatted = ModelOutputFormatter.format(llm_output)

    return RecommendationResponse(
        summary="Архитектурный анализ выполнен",
        findings=findings,
        model_summary=formatted.summary,
        recommendations=formatted.recommendations,
        raw_model_output=formatted.raw_output,
    )

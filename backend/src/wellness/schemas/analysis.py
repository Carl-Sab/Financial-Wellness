from pydantic import BaseModel


class MoodSpendCorrelationItem(BaseModel):
    mood: str
    pearson_r: float | None
    p_value: float | None
    n: int


class MoodSpendCorrelationResponse(BaseModel):
    transaction_count: int
    correlations: list[MoodSpendCorrelationItem]
    scatter_plot_png_base64: str | None = None
    bar_chart_png_base64: str | None = None
    ai_report_markdown: str | None = None

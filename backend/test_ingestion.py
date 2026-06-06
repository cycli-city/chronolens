from app.pipelines.ingestion import IngestionPipeline

# Use any PDF you have lying around - your resume, a sample contract, anything
pipeline = IngestionPipeline()

result = pipeline.ingest(
    file_path="sample.pdf",  # put a PDF file in backend/ folder named sample.pdf
    document_id="doc_001",
    version=1,
    timestamp="2024-01-15",
    doc_name="Sample Contract",
    doc_type="contract"
)

print(result)
print(f"\nTotal chunks in DB: {pipeline.vector_store.count()}")
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from models.usage_event import UsageEvent

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))

def process_embeddings():

    client = chromadb.HttpClient(
        host=os.getenv("CHROMA_HOST"),
        port=int(os.getenv("CHROMA_PORT")),
        settings=Settings(allow_reset=True)
    )

    embeddings = OpenAIEmbeddings(
        api_key=os.getenv("OPENAI_API_KEY")
    )

    vectorstore = Chroma(
        client=client,
        collection_name="usage_events",
        embedding_function=embeddings,
    )

    with Session(engine) as session:

        events = session.query(UsageEvent).filter_by(
            embedding_processed=False
        ).limit(200).all()

        docs = []

        for event in events:
            text = f"""
            Invoice ID: {event.invoice_id}
            Metric: {event.metric}
            Quantity: {event.quantity}
            Unit Price: {event.unit_price}
            Total Price: {event.total_price}
            Created At: {event.created_at}
            """

            docs.append(
                Document(
                    page_content=text,
                    metadata={
                        "event_id": str(event.id),
                        "invoice_id": str(event.invoice_id),
                        "metric": event.metric,
                    }
                )
            )

            event.embedding_processed = True

        if docs:
            vectorstore.add_documents(docs)

        session.commit()

    print(f"Embedded {len(docs)} usage events")


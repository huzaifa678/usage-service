from sqlalchemy.orm import Session
from models.usage_event import UsageEvent
from models.usage_aggregate import UsageAggregate
from sqlalchemy import engine 

def aggregate_usage_events():
    with Session(engine) as session:
        # Fetch unprocessed events
        events = session.query(UsageEvent).filter_by(processed=False).all()
        
        for event in events:
            # Aggregate per customer & metric
            aggregate = session.query(UsageAggregate).filter_by(
                customer_id=event.invoice_id, metric=event.metric
            ).first()
            
            if not aggregate:
                aggregate = UsageAggregate(
                    customer_id=event.invoice_id,
                    metric=event.metric,
                    daily_total=0,
                    monthly_total=0,
                    rolling_avg=0
                )
                session.add(aggregate)
            
            # Update aggregates
            aggregate.daily_total += event.quantity * float(event.unit_price)
            aggregate.monthly_total += event.quantity * float(event.unit_price)
            aggregate.rolling_avg = (aggregate.daily_total + aggregate.monthly_total) / 2
            
            event.processed = True
        
        session.commit() 
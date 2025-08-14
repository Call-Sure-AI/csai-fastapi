import asyncio
from app.db.postgres_client import get_db_connection

async def list_call_ids():
    try:
        async with await get_db_connection() as conn:
            print("=== CONVERSATION TABLE ===")
            conversation_query = "SELECT call_id, user_phone, agent_id, status, created_at FROM Conversation ORDER BY created_at DESC"
            conversation_rows = await conn.fetch(conversation_query)
            
            if conversation_rows:
                for row in conversation_rows:
                    print(f"Call ID: {row['call_id']}, Phone: {row['user_phone']}, Agent: {row['agent_id']}, Status: {row['status']}")
            else:
                print("No records found in Conversation table")
            
            print(f"\nTotal records in Conversation: {len(conversation_rows)}")
            
            print("\n=== CONVERSATION_OUTCOME TABLE ===")
            outcome_query = "SELECT call_id, user_phone, agent_id, outcome, created_at FROM Conversation_Outcome ORDER BY created_at DESC"
            outcome_rows = await conn.fetch(outcome_query)
            
            if outcome_rows:
                for row in outcome_rows:
                    print(f"Call ID: {row['call_id']}, Phone: {row['user_phone']}, Agent: {row['agent_id']}, Outcome: {row['outcome']}")
            else:
                print("No records found in Conversation_Outcome table")
            
            print(f"\nTotal records in Conversation_Outcome: {len(outcome_rows)}")
            
            # Show call_ids that exist in both
            conversation_ids = set(row['call_id'] for row in conversation_rows)
            outcome_ids = set(row['call_id'] for row in outcome_rows)
            
            print(f"\n=== SUMMARY ===")
            print(f"Call IDs in Conversation table: {list(conversation_ids)}")
            print(f"Call IDs in Conversation_Outcome table: {list(outcome_ids)}")
            print(f"Call IDs in both tables: {list(conversation_ids.intersection(outcome_ids))}")
            print(f"Call IDs only in Conversation: {list(conversation_ids - outcome_ids)}")
            print(f"Call IDs only in Conversation_Outcome: {list(outcome_ids - conversation_ids)}")
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(list_call_ids())

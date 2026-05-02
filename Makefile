# StreakBot — helper commands
# Usage: make install | make run | make reset | make check

.PHONY: install run reset check clean

install:
	pip install -r requirements.txt

run:
	python bot.py

# Reset all data (streak, reports, XP, lessons, sessions)
# WARNING: this deletes your streak history
reset:
	python -c "import os; [os.remove(f) for f in ['data.json','xp.json','lessons.json','sessions.json'] if os.path.exists(f)]; print('Data reset. All JSON files removed.')"

# Check that .env is configured
check:
	python -c "\
from dotenv import load_dotenv; import os; load_dotenv(); \
missing = [k for k in ['BOT_TOKEN','GROQ_API_KEY','GROUP_CHAT_ID','USER1_ID','USER2_ID'] if not os.getenv(k)]; \
print('Missing env vars:', missing) if missing else print('All env vars set correctly.')"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

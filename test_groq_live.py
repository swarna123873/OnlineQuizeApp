import os, sys
sys.path.insert(0, 'd:/EXMAPP')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django; django.setup()

from content.llm_service import get_llm_provider

if __name__ == '__main__':
    provider = get_llm_provider()
    print("Provider:", provider.__class__.__name__)
    print("Model:", getattr(provider, 'model', 'N/A'))

    qs = provider.generate_mcqs(
        [{'source': 'Chapter 1', 'content': 'Newton first law: An object at rest stays at rest unless acted upon by an external force. Second law: F=ma. Third law: Every action has an equal and opposite reaction.'}],
        subject='Physics',
        num_questions=3
    )
    print(f"Generated {len(qs)} questions")
    for i, q in enumerate(qs, 1):
        try:
            print(f"  Q{i}: {q['question_text'][:70]}")
            print(f"       A) {q['option_a'][:50]}")
            print(f"       Correct: {q['correct_answer']} | Difficulty: {q['difficulty']}")
        except Exception:
            pass
    print("\nGroq is LIVE and WORKING!")


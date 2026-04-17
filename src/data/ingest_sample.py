from database import DatabaseManager
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Ingestor")

def ingest_sample_data():
    db = DatabaseManager("maktaba_production.db")
    
    # 1. Add a Book
    book_id = db.add_book(
        title="Riyad as-Salihin (Sample Selection)",
        author="Imam an-Nawawi",
        language="multi",
        metadata={"category": "Hadith", "publisher": "Maktaba-OS"}
    )
    logger.info(f"Created Book ID: {book_id}")

    # 2. Add Chapters
    chapters = [
        {"title": "Chapter of Sincerity (Ikhlas)", "seq": 1},
        {"title": "Chapter of Repentance (Tawbah)", "seq": 2}
    ]

    for chap in chapters:
        chap_id = db.add_chapter(book_id, chap["title"], chap["seq"])
        logger.info(f"Created Chapter: {chap['title']} (ID: {chap_id})")

        # 3. Add Content Blocks (Arabic + Urdu + English)
        if chap["seq"] == 1:
            # Sample for Ikhlas
            db.add_content_block(chap_id, {
                "ar": "إِنَّمَا الأَعْمَالُ بِالنِّيَّاتِ",
                "ur": "اعمال کا دارومدار نیتوں پر ہے۔",
                "en": "Actions are but by intentions.",
                "reference": "Sahih al-Bukhari 1"
            })
            db.add_content_block(chap_id, {
                "ar": "وإِنَّمَا لِكُلِّ امْرِئٍ مَا نَوَى",
                "ur": "اور ہر شخص کے لیے وہی ہے جس کی اس نے نیت کی۔",
                "en": "And every person will have only what they intended.",
                "reference": "Sahih al-Bukhari 1"
            })
        
        elif chap["seq"] == 2:
            # Sample for Repentance
            db.add_content_block(chap_id, {
                "ar": "يَا أَيُّهَا النَّاسُ تُوبُوا إِلَى اللَّهِ",
                "ur": "اے لوگو! اللہ کی طرف توبہ کرو۔",
                "en": "O people, repent to Allah.",
                "reference": "Muslim"
            })

    logger.info("Sample data ingestion complete.")

if __name__ == "__main__":
    ingest_sample_data()

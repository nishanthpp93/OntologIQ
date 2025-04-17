import os
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, load_index_from_storage

import logging

from pdf_scraper import scrape_and_download_pdfs


def build_rag(directory):
    #Read text documents
    try:
        documents = SimpleDirectoryReader(directory).load_data()
    except Exception as e:
        logging.error(f"Error reading documents: {e}")
        return None

    #Index
    #LLama-index creates embedded vectors from the documents and stores them
    #From now on, it works only with the vectors
    index = VectorStoreIndex.from_documents(documents)

    #llama_index imports removed (already imported at the top)

    # Check if storage directory exists; if not, create it

    persist_dir = "./nccn_vectors"
    if not os.path.exists(persist_dir):

        os.makedirs(persist_dir)  # Create the directory
        # Create the index before persisting
        try:
            # Create the index before persisting
            index = VectorStoreIndex.from_documents(documents)

            index.storage_context.persist(persist_dir=persist_dir)  # Specify persist_dir here
        except Exception as e:
            logging.error(f"Error persisting index: {e}")
    else:
        try:
            # Load the existing index
            storage_context = StorageContext.from_defaults(persist_dir=persist_dir)
            index = load_index_from_storage(storage_context)
        except Exception as e:
            logging.error(f"Error loading index: {e}")
            return None


if __name__ == "__main__":
    directory = "./documents"  # Change this to your document directory
    if not os.path.exists(directory):
        os.makedirs(directory)
        scrape_and_download_pdfs(directory)
    else:
        build_rag(directory)

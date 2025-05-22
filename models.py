from sentence_transformers import SentenceTransformer, util

# Load BERT model (dùng mô hình nhẹ)
bert_model = SentenceTransformer('all-MiniLM-L6-v2')

def get_bert_embedding(text):
    return bert_model.encode(text, convert_to_tensor=True)

def find_similar_jobs(query, jobs, threshold=0.8, top_k=10):
    """Tìm công việc tương tự dựa trên ngữ nghĩa (BERT)"""
    # Xử lý trường hợp query rỗng
    if not query:
        # Nếu không có query, trả về các job có rating cao nhất
        sorted_jobs = sorted(jobs, key=lambda x: x.get('rating', 0), reverse=True)
        return sorted_jobs[:top_k]
        
    # Xử lý bình thường cho query không rỗng
    query_emb = get_bert_embedding(query)
    job_texts = [f"{row['title']} {row['job']} {row['pros']} {row['cons']}" for row in jobs]
    job_embs = bert_model.encode(job_texts, convert_to_tensor=True)
    cos_scores = util.pytorch_cos_sim(query_emb, job_embs)[0]
    results = []
    for idx, score in enumerate(cos_scores):
        if score >= threshold:
            results.append((jobs[idx], float(score)))
    results.sort(key=lambda x: x[1], reverse=True)
    return [r[0] for r in results[:top_k]]
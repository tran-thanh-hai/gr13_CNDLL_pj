from flask import Flask, render_template, request
from spark import get_spark_session, load_jobs_data
from models import find_similar_jobs
from pyspark.sql.functions import lower, col
import os
import math

app = Flask(__name__)
spark = get_spark_session()
csv_path = os.path.join(os.path.dirname(__file__), "data", "cleaned_df.csv")
JOBS_PER_PAGE = 20  # Số lượng kết quả mỗi trang

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/results", methods=["GET", "POST"])
def results():
    if request.method == "POST":
        # Lấy thông tin tìm kiếm từ form
        query = request.form.get("query", "")
        min_rating = float(request.form.get("min_rating", 0))
        min_career = float(request.form.get("min_career_opportunities", 0))
        min_compensation = float(request.form.get("min_compensation", 0))
        min_management = float(request.form.get("min_senior_management", 0))
        min_work_life = float(request.form.get("min_work_life", 0))
        min_culture = float(request.form.get("min_culture", 0))
        min_diversity = float(request.form.get("min_diversity", 0))
        recommend = request.form.get("recommend", "")
        ceo_approval = request.form.get("ceo_approval", "")
        business_outlook = request.form.get("business_outlook", "")
        page = 1  # Mặc định trang đầu tiên khi tìm kiếm mới
    else:
        # Lấy tham số từ URL (cho phân trang)
        query = request.args.get("query", "")
        min_rating = float(request.args.get("min_rating", 0))
        min_career = float(request.args.get("min_career", 0))
        min_compensation = float(request.args.get("min_compensation", 0))
        min_management = float(request.args.get("min_management", 0))
        min_work_life = float(request.args.get("min_work_life", 0))
        min_culture = float(request.args.get("min_culture", 0))
        min_diversity = float(request.args.get("min_diversity", 0))
        recommend = request.args.get("recommend", "")
        ceo_approval = request.args.get("ceo_approval", "")
        business_outlook = request.args.get("business_outlook", "")
        page = int(request.args.get("page", 1))
    
    # Tìm kiếm việc làm với các filter đã chọn
    all_jobs = search_jobs(
        query, min_rating, min_career, min_compensation, min_management, 
        min_work_life, min_culture, min_diversity, recommend, ceo_approval, business_outlook
    )
    
    # Tính toán phân trang
    total_jobs = len(all_jobs)
    total_pages = math.ceil(total_jobs / JOBS_PER_PAGE)
    start_idx = (page - 1) * JOBS_PER_PAGE
    end_idx = start_idx + JOBS_PER_PAGE
    jobs_to_display = all_jobs[start_idx:end_idx]
    
    # Hiển thị kết quả với phân trang
    return render_template(
        "results.html", 
        jobs=jobs_to_display, 
        total_jobs=total_jobs,
        query=query,
        min_rating=min_rating,
        min_career=min_career,
        min_compensation=min_compensation,
        min_management=min_management,
        min_work_life=min_work_life,
        min_culture=min_culture,
        min_diversity=min_diversity,
        recommend=recommend,
        ceo_approval=ceo_approval,
        business_outlook=business_outlook,
        current_page=page,
        total_pages=total_pages
    )

def search_jobs(query, min_rating=0, min_career=0, min_compensation=0, 
                min_management=0, min_work_life=0, min_culture=0, 
                min_diversity=0, recommend="", ceo_approval="", business_outlook=""):
    jobs_df = load_jobs_data(spark, csv_path)
    query_lower = query.lower()
    jobs = []

    # Áp dụng các bộ lọc cơ bản cho tất cả các truy vấn
    filtered_df = jobs_df.filter(col("rating") >= min_rating)
    
    # Áp dụng các bộ lọc
    if min_career > 0:
        filtered_df = filtered_df.filter(col("Career Opportunities") >= min_career)
    if min_compensation > 0:
        filtered_df = filtered_df.filter(col("Compensation and Benefits") >= min_compensation)
    if min_management > 0:
        filtered_df = filtered_df.filter(col("Senior Management") >= min_management)
    if min_work_life > 0:
        filtered_df = filtered_df.filter(col("Work/Life Balance") >= min_work_life)
    if min_culture > 0:
        filtered_df = filtered_df.filter(col("Culture & Values") >= min_culture)
    if min_diversity > 0:
        filtered_df = filtered_df.filter(col("Diversity & Inclusion") >= min_diversity)
    if recommend:
        filtered_df = filtered_df.filter(col("Recommend") == recommend)
    if ceo_approval:
        filtered_df = filtered_df.filter(col("CEO Approval") == ceo_approval)
    if business_outlook:
        filtered_df = filtered_df.filter(col("Business Outlook") == business_outlook)

    # Nếu query rỗng, trả về tất cả kết quả đã lọc
    if not query:
        return filtered_df.limit(100).collect()

    # 1. Job chứa chính xác từ khóa
    exact_regex = fr"\b{query_lower}\b"
    job_exact = filtered_df.filter(lower(filtered_df.job).rlike(exact_regex))
    jobs += job_exact.collect()

    # 2. Job chứa gần giống từ khóa (designer, designs, des,...)
    if len(jobs) < 100:
        contain_regex = f".*{query_lower}.*"
        job_contain = filtered_df.filter(lower(filtered_df.job).rlike(contain_regex))
        # Loại bỏ các job đã có ở bước trước
        jobs_ids = set((j['title'], j['job'], j['pros'], j['cons']) for j in jobs)
        job_contain = [j for j in job_contain.collect() if (j['title'], j['job'], j['pros'], j['cons']) not in jobs_ids]
        jobs += job_contain[:100-len(jobs)]

    # 3. Title chứa chính xác từ khóa
    if len(jobs) < 10:
        title_exact = filtered_df.filter(lower(filtered_df.title).rlike(exact_regex))
        jobs_ids = set((j['title'], j['job'], j['pros'], j['cons']) for j in jobs)
        title_exact = [j for j in title_exact.collect() if (j['title'], j['job'], j['pros'], j['cons']) not in jobs_ids]
        jobs += title_exact[:10-len(jobs)]

    # 4. Title chứa gần giống từ khóa
    if len(jobs) < 10:
        title_contain = filtered_df.filter(lower(filtered_df.title).rlike(contain_regex))
        jobs_ids = set((j['title'], j['job'], j['pros'], j['cons']) for j in jobs)
        title_contain = [j for j in title_contain.collect() if (j['title'], j['job'], j['pros'], j['cons']) not in jobs_ids]
        jobs += title_contain[:10-len(jobs)]

    # 5. Pros chứa chính xác từ khóa
    if len(jobs) < 10:
        pros_exact = jobs_df.filter(lower(jobs_df.pros).rlike(exact_regex)).filter(jobs_df.rating >= min_rating)
        if recommend:
            pros_exact = pros_exact.filter(jobs_df.Recommend == recommend)
        if ceo_approval:
            pros_exact = pros_exact.filter(jobs_df["CEO Approval"] == ceo_approval)
        if business_outlook:
            pros_exact = pros_exact.filter(jobs_df["Business Outlook"] == business_outlook)
        jobs_ids = set((j['title'], j['job'], j['pros'], j['cons']) for j in jobs)
        pros_exact = [j for j in pros_exact.collect() if (j['title'], j['job'], j['pros'], j['cons']) not in jobs_ids]
        jobs += pros_exact[:10-len(jobs)]

    # 6. Pros chứa gần giống từ khóa
    if len(jobs) < 10:
        pros_contain = jobs_df.filter(lower(jobs_df.pros).rlike(contain_regex)).filter(jobs_df.rating >= min_rating)
        if recommend:
            pros_contain = pros_contain.filter(jobs_df.Recommend == recommend)
        if ceo_approval:
            pros_contain = pros_contain.filter(jobs_df["CEO Approval"] == ceo_approval)
        if business_outlook:
            pros_contain = pros_contain.filter(jobs_df["Business Outlook"] == business_outlook)
        jobs_ids = set((j['title'], j['job'], j['pros'], j['cons']) for j in jobs)
        pros_contain = [j for j in pros_contain.collect() if (j['title'], j['job'], j['pros'], j['cons']) not in jobs_ids]
        jobs += pros_contain[:10-len(jobs)]

    # 7. Cons chứa chính xác từ khóa
    if len(jobs) < 10:
        cons_exact = jobs_df.filter(lower(jobs_df.cons).rlike(exact_regex)).filter(jobs_df.rating >= min_rating)
        if recommend:
            cons_exact = cons_exact.filter(jobs_df.Recommend == recommend)
        if ceo_approval:
            cons_exact = cons_exact.filter(jobs_df["CEO Approval"] == ceo_approval)
        if business_outlook:
            cons_exact = cons_exact.filter(jobs_df["Business Outlook"] == business_outlook)
        jobs_ids = set((j['title'], j['job'], j['pros'], j['cons']) for j in jobs)
        cons_exact = [j for j in cons_exact.collect() if (j['title'], j['job'], j['pros'], j['cons']) not in jobs_ids]
        jobs += cons_exact[:10-len(jobs)]

    # 8. Cons chứa gần giống từ khóa
    if len(jobs) < 10:
        cons_contain = jobs_df.filter(lower(jobs_df.cons).rlike(contain_regex)).filter(jobs_df.rating >= min_rating)
        if recommend:
            cons_contain = cons_contain.filter(jobs_df.Recommend == recommend)
        if ceo_approval:
            cons_contain = cons_contain.filter(jobs_df["CEO Approval"] == ceo_approval)
        if business_outlook:
            cons_contain = cons_contain.filter(jobs_df["Business Outlook"] == business_outlook)
        jobs_ids = set((j['title'], j['job'], j['pros'], j['cons']) for j in jobs)
        cons_contain = [j for j in cons_contain.collect() if (j['title'], j['job'], j['pros'], j['cons']) not in jobs_ids]
        jobs += cons_contain[:10-len(jobs)]

    # 9. Nếu vẫn chưa đủ, dùng BERT/content-based filtering
    if len(jobs) < 100:  # Tăng số lượng kết quả
        all_jobs = filtered_df.collect()
        jobs_ids = set((j['title'], j['job'], j['pros'], j['cons']) for j in jobs)
        remain_jobs = [j for j in all_jobs if (j['title'], j['job'], j['pros'], j['cons']) not in jobs_ids]
        jobs += find_similar_jobs(query, remain_jobs, threshold=0.0, top_k=100-len(jobs))

    return jobs

if __name__ == "__main__":
    app.run(debug=True)
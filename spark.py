from pyspark.sql import SparkSession

def get_spark_session():
    return SparkSession.builder \
        .appName("Job_Recommendation") \
        .getOrCreate()

def load_jobs_data(spark, csv_path):
    return spark.read.csv(csv_path, header=True, inferSchema=True)

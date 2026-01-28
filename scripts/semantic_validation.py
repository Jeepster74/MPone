import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
import os

# Settings
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
INPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "karting_enriched.csv")

# Negative keywords for pure "leisure" clusters (if they appear too much)
NO_GO_KEYWORDS = ['boat', 'rental', 'pedalo', 'paddle', 'golf', 'minigolf', 'bowling', 'laser', 'tag', 'paintball']
REQUIRED_KEYWORDS = ['kart', 'karting', 'circuit', 'track', 'race', 'racing', 'fast']

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    df = pd.read_csv(INPUT_FILE)
    
    # We only care about records with review snippets
    df_snippets = df[df['Top Reviews Snippet'].notna() & (df['Top Reviews Snippet'] != 'N/A')]
    
    if df_snippets.empty:
        print("No snippets found for semantic validation.")
        return
        
    print(f"Analyzing {len(df_snippets)} snippets for semantic clusters...")
    
    # TF-IDF Vectorization
    vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
    X = vectorizer.fit_transform(df_snippets['Top Reviews Snippet'])
    
    # KMeans Clustering (e.g. 5 clusters)
    # We aim to find the "purely karting" clusters vs "mixed leisure" clusters
    num_clusters = min(5, len(df_snippets))
    kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
    df_snippets['cluster'] = kmeans.fit_predict(X)
    
    # Identify "Suspicious" clusters
    # A cluster is suspicious if it has high count of NO_GO_KEYWORDS and low REQUIRED_KEYWORDS
    to_remove = set()
    
    for i in range(num_clusters):
        cluster_data = df_snippets[df_snippets['cluster'] == i]
        all_text = " ".join(cluster_data['Top Reviews Snippet']).lower()
        
        no_go_score = sum(all_text.count(k) for k in NO_GO_KEYWORDS)
        req_score = sum(all_text.count(k) for k in REQUIRED_KEYWORDS)
        
        print(f"Cluster {i}: {len(cluster_data)} records | No-Go: {no_go_score} | Req: {req_score}")
        
        # Heuristic: If it's dominated by non-karting terms, flag the whole cluster for manual review
        # or remove if very strong evidence
        if no_go_score > req_score * 1.5:
             print(f"  !!! Cluster {i} appears to be NON-KARTING leisure. Removing.")
             to_remove.update(cluster_data.index)
        else:
             # Even in good clusters, individual records might be bad
             for idx, row in cluster_data.iterrows():
                 text = str(row['Top Reviews Snippet']).lower()
                 if any(k in text for k in ['boat rental', 'pedalo', 'minigolf']):
                      if not any(k in text for k in ['karting', 'track']):
                           print(f"  - Individual Remove: {row['Name']} (Snippet: {text[:50]}...)")
                           to_remove.add(idx)

    if not to_remove:
        print("No semantic anomalies found.")
    else:
        df_final = df.drop(index=list(to_remove))
        print(f"\nRemoved {len(to_remove)} semantic anomalies.")
        print(f"Final count: {len(df_final)}")
        df_final.to_csv(OUTPUT_FILE, index=False)
        print(f"Cleaned dataset saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()

"""Local-first semantic test. Model downloaded once. No CV data is uploaded by this script."""
import argparse

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',default='intfloat/multilingual-e5-small')
    args=parser.parse_args()
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise SystemExit('Install optional dependencies: pip install sentence-transformers')
    model=SentenceTransformer(args.model,device='cpu')
    phrases=['query: Backend developer Python Docker Flask',
             'passage: Python Flask backend engineer building Docker services',
             'passage: Visual designer specializing in typography']
    vectors=model.encode(phrases,normalize_embeddings=True)
    if vectors.shape!=(3,384):raise SystemExit('Unexpected embedding dimension: '+str(vectors.shape))
    sims=(float(vectors[0]@vectors[1]),float(vectors[0]@vectors[2]))
    print('Model:',args.model,'dimensions:',vectors.shape[1], 'relevant:',round(sims[0],3),'unrelated:',round(sims[1],3))
    if sims[0]<=sims[1]:raise SystemExit('Semantic ranking smoke test failed')
    print('PASS: relevant passage ranks higher; this is NOT a model-quality benchmark')
if __name__=='__main__':main()

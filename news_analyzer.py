import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from datetime import datetime
import pytz
from docx import Document
import io

# Set up the Streamlit app
st.title("AI News Analyzer")
st.markdown("""
Scrapes latest AI trends/news and do detailed analysis.
""")

def create_word_file(text):
    doc = Document()
    doc.add_paragraph(text)  # Adds the entire post as a single paragraph
    doc_io = io.BytesIO()
    doc.save(doc_io)
    doc_io.seek(0)
    return doc_io

# Initialize session state variables
if 'articles' not in st.session_state:
    st.session_state.articles = []
if 'selected_article' not in st.session_state:
    st.session_state.selected_article = None
if 'generated_post' not in st.session_state:
    st.session_state.generated_post = ""

# Configuration section
with st.sidebar:
    st.header("Configuration")
    
    # API Keys
    gemini_api_key = "AIzaSyCICpSXuCPzAGVT4VdDIqFQysch3w-irec"#st.text_input("Google Gemini API Key", type="password")
    #medium_api_key = st.text_input("Medium API Key (optional)", type="password")
    
    # Scraping options
    st.subheader("Scraping Options")
    num_articles = st.slider("Number of articles to fetch", 3, 15, 5)
    sources = st.multiselect(
        "Select news sources",
        ["TechCrunch AI", "ArXiv Recent AI Papers"],
    )
    
    # Post generation options
    st.subheader("Detailed Analysis Style")
    tone = st.selectbox("Writing Tone", ["Professional", "Casual", "Technical", "Conversational"], index=0)
    post_length = st.selectbox("Post Length", ["Short (300 words)", "Medium (500 words)", "Long (800 words)"], index=1)
    model_type = st.selectbox("Gemini Model", ["gemini-2.5-pro-exp-03-25", "gemini-2.0-flash"], index=0)

def scrape_techcrunch():
    """Scrape TechCrunch AI articles"""
    url = "https://techcrunch.com/category/artificial-intelligence/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        articles = []
        
        # Find all article items
        for item in soup.select('li.wp-block-post')[:num_articles]:
            # Extract title and link
            title_element = item.select_one('h3.loop-card__title a')
            if not title_element:
                continue
                
            title = title_element.get_text(strip=True)
            link = title_element['href']
            
            # Extract summary/excerpt
            excerpt = item.select_one('div.loop-card__meta time').find_next_sibling(string=True)
            if excerpt:
                excerpt = excerpt.get_text(strip=True) + "..."
                #print(excerpt)
            else:
                excerpt = ""
            
            # Extract date
            date_element = item.select_one('time.loop-card__time')
            date = date_element['datetime'] if date_element else ""

             # --- NEW: Fetch full article content ---
            try:
                article_response = requests.get(link, headers=headers)
                if article_response.status_code == 200:
                    article_soup = BeautifulSoup(article_response.text, 'html.parser')
                    
                    # Find the main article content (TechCrunch-specific)
                    content_div = article_soup.select_one('div.entry-content')
                    if content_div:
                        # Remove unwanted elements (ads, share buttons, etc.)
                        for element in content_div.select('.ad-unit, .marfeel-experience-inline-cta, .wp-block-tc23-podcast-player'):
                            element.decompose()
                        
                        # Get clean text content
                        content = "\n".join(
                            p.get_text(strip=True) 
                            for p in content_div.find_all(['p', 'h2', 'h3']) 
                            if p.get_text(strip=True)
                        )
                    else:
                        content = excerpt
                else:
                    content = f"Failed to fetch article (HTTP {article_response.status_code})"
            except Exception as e:
                content = f"Error fetching content: {str(e)}"
            
            # Extract source/category
            category = item.select_one('a.loop-card__cat')
            source = category.get_text(strip=True) if category else "TechCrunch AI"
            articles.append({
                'title': title,
                'url': link,
                'summary': content,
                'date': date,
                'source': source
            })
        
        return articles
    
    except Exception as e:
        print(f"Error scraping TechCrunch: {e}")
        return []

# def scrape_venturebeat():
#     """Scrape VentureBeat AI articles"""
#     url = "https://venturebeat.com/category/ai/"
#     headers = {'User-Agent': 'Mozilla/5.0'}
    
#     try:
#         response = requests.get(url, headers=headers)
#         soup = BeautifulSoup(response.text, 'html.parser')
#         articles = []
        
#         for item in soup.select('article.ArticleListing')[:num_articles]:
#             title = item.select_one('h2.ArticleListing__title a').get_text(strip=True)
#             link = item.select_one('h2.ArticleListing__title a')['href']
#             excerpt = item.select_one('div.ArticleListing__excerpt').get_text(strip=True)[:150] + "..."
#             date = item.select_one('time.ArticleListing__time')['datetime']
            
#             articles.append({
#                 'title': title,
#                 'url': link,
#                 'summary': excerpt,
#                 'date': date,
#                 'source': 'VentureBeat AI'
#             })
        
#         return articles
    
#     except Exception as e:
#         st.error(f"Error scraping VentureBeat: {e}")
#         return []


import requests
from bs4 import BeautifulSoup

def scrape_arxiv_recent():
    """Scrape recent AI papers from ArXiv with combined HTML content in summary"""
    url = "https://arxiv.org/list/cs.AI/recent"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        articles = []
        
        # Find all paper entries
        dt_items = soup.find_all('dt', limit=num_articles)
        
        for dt in dt_items:
            article = {
                'source': 'ArXiv AI Papers',
                'date': '',
                'summary': '',
                'url': '',
                'title': ''
            }
            
            try:
                dd = dt.find_next_sibling('dd')
                if not dd:
                    continue
                
                # Extract arXiv ID and link
                abstract_link = dt.find('a', {'title': 'Abstract'})
                if not abstract_link:
                    continue
                    
                arxiv_id = abstract_link['href'].split('/')[-1]
                article['url'] = f"https://arxiv.org/abs/{arxiv_id}"
                
                # Extract title
                title_div = dd.find('div', class_='list-title')
                article['title'] = (
                    title_div.get_text(strip=True).replace("Title:", "").strip()
                    if title_div else "Untitled"
                )
                
                # Extract authors
                authors_div = dd.find('div', class_='list-authors')
                authors = (
                    authors_div.get_text(strip=True).replace("Authors:", "").strip()
                    if authors_div else "Unknown authors"
                )
                
                # Extract date
                date_div = dd.find('div', class_='list-date')
                article['date'] = (
                    date_div.get_text(strip=True)
                    if date_div else "Date not available"
                )
                
                # Get HTML content if available
                html_link = dt.find('a', {'title': 'View HTML'})
                html_text = ""
                html_preview = ""
                if html_link and html_link.has_attr('href'):
                    try:
                        html_response = requests.get(html_link['href'], headers=headers, timeout=10)
                        if html_response.status_code == 200:
                            html_text = BeautifulSoup(html_response.text, 'html.parser').get_text()
                            html_preview = "\n\n**HTML Preview:** " + html_text[:10000].replace("\n", " ") + "..."
                    except Exception:
                        pass  # Silently skip if HTML can't be fetched
                
                # Combine everything into summary
                article['summary'] = f"""
                **Authors:** {authors}
                {html_preview}
                """
                article['htmltext'] = html_text
                
                articles.append(article)
                
            except Exception:
                continue  # Skip problematic entries
        
        return articles
    
    except requests.RequestException:
        return []
    except Exception:
        return []


def fetch_articles():
    """Fetch articles from selected sources"""
    all_articles = []
    
    if "TechCrunch AI" in sources:
        all_articles.extend(scrape_techcrunch())
    
    # if "VentureBeat AI" in sources:
    #     all_articles.extend(scrape_venturebeat())
    
    if "ArXiv Recent AI Papers" in sources:
        all_articles.extend(scrape_arxiv_recent())
    
    # Sort articles by date (newest first)
    all_articles.sort(key=lambda x: x['date'], reverse=True)
    
    return all_articles[:num_articles]

def generate_medium_post_with_gemini(article, gemini_api_key):
    """Generate a Medium post using Google Gemini based on the article"""
    if not gemini_api_key:
        st.error("Please enter your Google Gemini API key")
        return ""
    
    try:
        # Configure Gemini
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel(model_type)
        html_text = ""
        content = ""
        
        # Determine word count
        if "Short" in post_length:
            word_count = 300
        elif "Medium" in post_length:
            word_count = 500
        else:
            word_count = 800

        if article['source'] == "ArXiv AI Papers":
            html_text = article['htmltext']
        content = article['summary'] + html_text
        prompt = f"""
  Write a {tone.lower()} blog post about the following AI news/article, ensuring it is engaging and accessible to non-technical users. The blog should have a reading time of approximately 12-15 minutes.

**Article Details:**
- **Title:** {article['title']}
- **Source:** {article['source']}
- **Content:** {content[:10000]}
- **URL:** {article['url']}

### **Post Structure:**

#### **1. Engaging Introduction**
- Start with a strong hook: an interesting fact, a question, or a relatable scenario.
- Clearly explain why this AI news is important for everyday users.

#### **2. Article Content in Simple Terms**
- Break down the key takeaways into a digestible format.
- Use simple language and avoid technical jargon.

#### **3. In-Depth Analysis with Real-World Examples**
- Explain the broader implications of this news in a way that connects with users.
- Use storytelling techniques to make the content engaging.
- **Search the web and embed relevant links to the post.*
- If there is a possiblity for comparison then compare and display in  well structured tables.
-Include real-world use cases and practical applications.

### **4. Multimedia Enhancements**
- **Embed relevant images in the post using Markdown format**  
  Example: `![Alt Text](https://example.com/image.jpg)`

- **Embed relevant YouTube videos using an HTML iframe inside Markdown**  
  Example:<iframe width="560" height="315" src="https://www.youtube.com/embed/VIDEO_ID" frameborder="0" allowfullscreen></iframe>

5. Breaking Down AI for Non-Tech Users
Answer 5-15 common user questions in a Q&A style or bullet points.s.
Relate AI advancements to everyday life (e.g., "How does this affect your job, shopping, or daily routine?").

6. Engaging Conclusion
End with a thought-provoking statement or encourage discussion.

#### Formatting
Use short paragraphs and bold key points for easy reading.

Naturally integrate keywords related to AI, technology, and the specific news topic.

Add relevant hashtags at the end (e.g., #AI #TechNews #FutureOfAI).
        """
        
        response = model.generate_content(prompt)
        return response.text
    
    except Exception as e:
        st.error(f"Error generating post with Gemini: {e}")
        return ""

# def post_to_medium(title, content, api_key):
#     """Post to Medium using their API"""
#     if not api_key:
#         st.error("Medium API key not provided")
#         return False
    
#     # This is a placeholder - you would need to implement the actual Medium API integration
#     # Medium's API requires OAuth2 authentication and has specific endpoints for posting
    
#     try:
#         # Here you would implement the actual API call to Medium
#         # For now, we'll just simulate it
#         st.success(f"Post '{title}' would be published to Medium (simulated)")
#         return True
#     except Exception as e:
#         st.error(f"Error posting to Medium: {e}")
#         return False

# Main app functionality
tab1,tab2 = st.tabs(["AI News & Articles","Stocks Stories"])

with tab1:
    st.header("Fetch Latest AI Articles")
    if st.button("Scrape Articles"):
        with st.spinner("Fetching latest AI trends..."):
            st.session_state.articles = fetch_articles()
    
    if st.session_state.articles:
        st.success(f"Found {len(st.session_state.articles)} articles")
        
        for i, article in enumerate(st.session_state.articles):
            with st.expander(f"{i+1}. {article['title']}"):
                st.session_state.generated_post = None
                st.markdown(f"**Source:** {article['source']}")
                st.markdown(f"**Date:** {article['date']}")
                st.markdown(f"**Summary:** {article['summary']}")
                st.markdown(f"[Read original article]({article['url']})")
                if st.button(f"Select for Detaled Analysis", key=f"select_{i}"):
                    st.session_state.selected_article = article
                    with st.spinner("Analyzing...."):
                        st.session_state.generated_post = generate_medium_post_with_gemini(st.session_state.selected_article,gemini_api_key)

                if st.session_state.generated_post:
                    st.subheader("Detailed Analysis")
                    st.markdown(st.session_state.generated_post,unsafe_allow_html=True)
                    docx_file = create_word_file(st.session_state.generated_post)
                    # Add download button
                    st.download_button(
                        label="Download Post as Word",
                        data=docx_file,
                        file_name=f"medium_post_{datetime.now().strftime('%Y%m%d')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"word_download_button_{i}"
                    )
import argparse
from bs4 import BeautifulSoup
from bs4.element import Tag

# Function to convert HTML to Markdown-like format
def html_to_markdown(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    markdown = []
    
    # Loop through all the tags and text in the order they appear
    for element in soup.descendants:
        # Skip elements that are NavigableStrings (like spaces or newlines)
        if element.name:
            # Convert <h1> to # Header
            if element.name == 'h1':
                markdown.append(f"# {element.get_text(strip=True)}\n")
            
            # Convert <h2> to ## Header
            elif element.name == 'h2':
                markdown.append(f"## {element.get_text(strip=True)}\n")
            
            # Convert <h3> to ### Header
            elif element.name == 'h3':
                markdown.append(f"### {element.get_text(strip=True)}\n")
            
            # Convert <p> to paragraphs, process inline code
            elif element.name == 'p':
                paragraph_text = ""
                for child in element.children:
                    if child.name == 'code':
                        # Append inline code with backticks
                        paragraph_text += f"`{child.get_text(strip=True)}`"
                    else:
                        # Append regular text
                        paragraph_text += child.get_text(strip=True)
                markdown.append(f"{paragraph_text}\n")
            
            # Convert <li> to markdown list items
            elif element.name == 'li':
                markdown.append(f"- {element.get_text(strip=True)}\n")
            
            # Handle <pre><code> or standalone <code> elements for block code
            elif element.name == 'pre' and element.code:
                # Get block code inside <pre><code>
                # For standalone block code, we need to handle inline elements properly and preserve newlines
                code_text = ""
                for child in element.children:
                    for sub_child in child.children:
                        if sub_child.name == 'br':
                            code_text += "\n"
                        else:
                            code_text += f"`{sub_child.get_text()}`"
                markdown.append(f"\n```\n{code_text}\n```\n")
    return '\n'.join(markdown)

# Function to read HTML file and convert to Markdown
def convert_html_file_to_markdown(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        html_content = file.read()
    
    # Convert the HTML content to Markdown
    markdown_content = html_to_markdown(html_content)
    
    # Save the Markdown content to a new file
    markdown_file_path = file_path.replace(".html", ".md")
    with open(markdown_file_path, 'w', encoding='utf-8') as markdown_file:
        markdown_file.write(markdown_content)
    
    print(f"Markdown content has been saved to {markdown_file_path}")

if __name__ == "__main__":
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Convert HTML file to Markdown.")
    parser.add_argument("file", help="The path to the HTML file to convert.")
    
    # Parse command-line arguments
    args = parser.parse_args()
    
    # Convert the specified file
    convert_html_file_to_markdown(args.file)

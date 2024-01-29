import datetime
import streamlit as st
import pandas as pd
import requests
from lxml import html
from bs4 import BeautifulSoup
import re
from itertools import chain, permutations
import io
from io import BytesIO
from datetime import datetime, timedelta
import pytz
#from pyxlsb import open_workbook as open_xlsb

buffer = io.BytesIO()

def get_data_from_url(url,tab):
    response = requests.get(url)

    if response.status_code == 200:
        # Parse the HTML content of the page using lxml
        tree = html.fromstring(response.content)

        # Define the XPath to find the table within tbody
        xpath = f'//*[@id="anx_1"]/table[{tab}]'

        # Find the table using XPath
        table = tree.xpath(xpath)

        # Check if the table is found
        if table:
            # Extract data from the table
            rows = table[0].xpath('.//tr')

            # Create lists to store data
            data = []
            for row in rows:
                columns = row.xpath('.//th|td')
                data.append([col.text_content().strip() for col in columns])

            # Create a DataFrame from the data
            df = pd.DataFrame(data)
            return df

    return None

def data_manipulation(df):

    df.columns = ['Num', 'Name', 'Identifying information', 'Reasons', 'Date of listing']
    stopword = 'Name'
    stop_column = 'Name'

    # Find the index where the stopword is first encountered
    stop_index = df.index[df[stop_column] == stopword].tolist()

    if stop_index:
        df = df.iloc[stop_index[0] + 1:]
    df = df[['Name', 'Identifying information']]

    date_pattern = r'(\d{1,2}\.\d{1,2}\.\d{4})|\b(\d{4})\b'

    df['Date'] = df['Identifying information'].apply(
        lambda x: re.search(date_pattern, x).group(0) if re.search(date_pattern, x) else None)
    df.drop('Identifying information', inplace=True, axis=1)

    df[['Name', 'AKA']] = df['Name'].str.split('\n', expand=True)
    df['AKA'] = df['AKA'].astype(str).str.replace('(a.k.a. ', '').str.replace(')', '')

    aka = df[['AKA', 'Date']][df['AKA'] != 'None']
    aka.columns = ['Name', 'Date']

    full = pd.concat([df[['Name', 'Date']], aka], ignore_index=True)
    full['Name'] = full['Name'].apply(lambda x: x.strip())

        # Function to generate all variations of a name
    def generate_name_variations(name):
        parts = name.split()
        return list(chain.from_iterable(permutations(parts, r) for r in range(1, len(parts) + 1)))

        # Create a list to store the rows of the new DataFrame
    new_rows = []

        # Iterate over each row in the original DataFrame
    for _, row in full.iterrows():
        name_variations = generate_name_variations(row['Name'])
        for variation in name_variations:
            new_rows.append({'Name': row['Name'], 'Name_Variations': ' '.join(variation)})

        # Create a new DataFrame from the list of rows
    new_df = pd.DataFrame(new_rows)

    fin_df = new_df.merge(full, on='Name', how='left')


    return fin_df



def to_excel(df):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Sheet1')
    workbook = writer.book
    worksheet = writer.sheets['Sheet1']
    format1 = workbook.add_format({'num_format': '0.00'}) 
    worksheet.set_column('A:A', None, format1)  
    writer.close()
    processed_data = output.getvalue()
    return processed_data



def get_data_from_usa_url(url):
    # Send a GET request to the specified URL
    response = requests.get(url)
    
    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        # Parse the HTML content of the page
        soup = BeautifulSoup(response.content, "html.parser")

        # Find all div elements with class "field__item"
        target_elements = soup.find_all("div", class_="field__item")

        # Create empty lists to store the text content for each DataFrame
        paragraphs3_texts = []
        paragraphs4_texts = []
        paragraphs5_texts = []

        # Iterate through each target element
        for element in target_elements:
            p3 = element.find_all("p")[2] if len(element.find_all("p")) >= 3 else None
            p4 = element.find_all("p")[3] if len(element.find_all("p")) >= 4 else None
            p5 = element.find_all("p")[4] if len(element.find_all("p")) >= 5 else None

            if p3:
                paragraphs3_texts.extend(p3.find_all(text=True))  # Extract all text elements
            if p4:
                paragraphs4_texts.extend(p4.find_all(text=True))
            if p5:
                paragraphs5_texts.extend(p5.find_all(text=True))

        # Create DataFrames with each text element as a separate row
        df3 = pd.DataFrame(paragraphs3_texts, columns=["Text"])
        df4 = pd.DataFrame(paragraphs4_texts, columns=["Text"])
        df5 = pd.DataFrame(paragraphs5_texts, columns=["Text"])

        return df3, df4, df5

    else:
        # If the request was not successful, print an error message
        print(f"Error: Unable to retrieve data from {url}")
        return None, None, None


def remove_rows_by_text(df, text_to_remove):
    df_filtered = df[df['Text'] != text_to_remove].reset_index(drop=True)
    return df_filtered
    
def extract_first_word(text):
    words = text.split(',')
    return words[0] if words else None

def add_surname_column(df):
    df['Surname'] = df['Text'].apply(extract_first_word)


def extract_first_names(input_string):
    # Define a pattern to capture the names
    pattern = re.compile(r'[A-Z]+,\s([^,(]+)(?:\(|,)')

    # Find the first match in the input text
    match = re.search(pattern, input_string)

    # Extract the desired name
    if match:
        name = match.group(1).strip()
        return name
    else:
        return None


def add_full_name_column(df):
    df['Full Name'] = df['Text'].apply(lambda x: extract_first_names(x))


def extract_names_from_akas(df, input_text):
    aka_pattern = re.compile(r'\(a\.k\.a\.[^)]+\)')

    aka_matches = re.findall(aka_pattern, input_text)

    name_pattern = re.compile(r'a\.k\.a\. (.*?)(?=;|\))')

    extracted_names = [re.findall(name_pattern, aka_match) for aka_match in aka_matches]

    flattened_names = [name for sublist in extracted_names for name in sublist]

    full_name = df[df['Text'] == input_text]['Full Name'].iloc[0]
    flattened_names.append(full_name)

    return flattened_names

def add_surname_to_column(df):
    df['All Names'] = df['Text'].apply(lambda x: extract_names_from_akas(df,x))


def process_all_names_column(df):
    # Apply the processing logic to the 'All Names' column
    df['All Names'] = df['All Names'].apply(lambda x: x[1:-1].split(", "))
    return df


def expand_list_column(df, list_column, other_columns):
    expanded_rows = []
    for index, row in df.iterrows():
        names_list = row[list_column]
        other_values = {col: row[col] for col in other_columns}
        for name in names_list:
            row_data = {list_column: name, **other_values}
            expanded_rows.append(row_data)

    expanded_df = pd.DataFrame(expanded_rows)
    return expanded_df


def generate_name_all_variations(df, column_name):
    def generate_name_variations(name):
        parts = name.split()
        return list(chain.from_iterable(permutations(parts, r) for r in range(1, len(parts) + 1)))

    # Create a list to store the rows of the new DataFrame
    new_rows = []

    # Iterate over each row in the original DataFrame
    for _, row in df.iterrows():
        name_variations = generate_name_variations(row[column_name])
        for variation in name_variations:
            new_rows.append({column_name: row[column_name], f'{column_name}_Variations': ' '.join(variation)})

    # Create a new DataFrame from the list of rows
    new_df = pd.DataFrame(new_rows)

    return new_df






# Streamlit App
st.title("EU and USA restricrions data scraping")

# Input for URL
url_eu = st.text_input("Enter URL EU:", 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ:L_202400380')
url_USA = st.text_input("Enter URL USA:", 'https://ofac.treasury.gov/recent-actions/20231212')

# Button to trigger the process
if st.button("Process"):
    df_1 = get_data_from_url(url_eu,1)
    df_2 = get_data_from_url(url_eu,2)


    df_3, df_4, df_5 = get_data_from_usa_url(url_USA)


    if df_1 is not None and df_2 is not None:
        # DataFrame Manipulation
        persons = data_manipulation(df_1)
        entity = data_manipulation(df_2)

        df3 = remove_rows_by_text(df_3, 'RSS Feed Validator')
        add_surname_column(df3)
        add_full_name_column(df3)
        add_surname_to_column(df3)
        df3['All Names'] = df3['All Names'].astype(str).str.replace("'", "")
        process_all_names_column(df3)
        names_df3  = expand_list_column(df3,'All Names',['Full Name','Surname'])
        individuals_us = generate_name_all_variations(names_df3,'All Names')






        # Download buttons for Excel files
        xlsx_1 = to_excel(persons)
        xlsx_2 = to_excel(entity)

        xlsx_3 = to_excel(individuals_us)



        now = datetime.now(pytz.timezone('Asia/Tbilisi')).strftime('%d_%m_%Y_%H_%M_%S')

        # Display DataFrames side by side
        col1, col2 = st.columns(2)
        with col1:
            st.write("EU Persons Restrictions:")
            #st.write(persons)

        with col2:
            st.write("EU Entity Restrictions:")
            #st.write(entity)


        col1.download_button(
            label="Download EU Persons Excel",
            data=xlsx_1,
            file_name=f"EU_persons_restrictions_{now}.xlsx",
            mime='application/vnd.ms-excel'
        )

        col2.download_button(
            label="Download EU Entity Excel",
            data=xlsx_2,
            file_name=f"EU_entity_restrictions_{now}.xlsx",
            mime='application/vnd.ms-excel'
        )

        with col1:
            st.write(persons)

        with col2:
            st.write(entity)

        with col1:
            st.write("USA Persons Restrictions:")

        col1.download_button(
            label="Download USA Persons Excel",
            data=xlsx_3,
            file_name=f"USA_persons_restrictions_{now}.xlsx",
            mime='application/vnd.ms-excel'
        )

        with col1:
            st.write(individuals_us)




        

    else:
        st.write("Failed to retrieve one or both pages. Please check the URL.")


    

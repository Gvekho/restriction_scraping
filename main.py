import datetime
import streamlit as st
import pandas as pd
import requests
from lxml import html
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





# Streamlit App
st.title("EU and USA restricrions data scraping")

# Input for URL
url = st.text_input("Enter URL:", 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ:L_202400380')

# Button to trigger the process
if st.button("Process"):
    df_1 = get_data_from_url(url,1)
    df_2 = get_data_from_url(url,2)

    if df_1 is not None:
        #st.write("Data Extracted:")
        #st.write(df)

        # DataFrame Manipulation

        persons = data_manipulation(df_1)

        st.write("EU Persons Restricrions:")
        st.write(persons)

        #@st.cache


        #def convert_df(df):
        #    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            # IMPORTANT: Cache the conversion to prevent computation on every rerun
        #        return df.to_excel(Writer,sheet_name='Sheet1', index=False)#.encode('utf-8')

        xlsx_1 = to_excel(persons)

        now = datetime.now(pytz.timezone('Asia/Tbilisi')).strftime('%d_%m_%Y_%H_%M_%S')

        # Button to download CSV
        st.download_button(label = "Download EU Excel", data=xlsx_1, file_name=f"EU_restrictions_{now}.xlsx", mime='application/vnd.ms-excel',)

    else:
        st.write("Failed to retrieve the page. Please check the URL.")


    if df_2 is not None:
        #st.write("Data Extracted:")
        #st.write(df)

        # DataFrame Manipulation
        entity = data_manipulation(df_2)

        st.write("EU Entity Restricrions:")
        st.write(entity)

        #@st.cache


        #def convert_df(df):
        #    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            # IMPORTANT: Cache the conversion to prevent computation on every rerun
        #        return df.to_excel(Writer,sheet_name='Sheet1', index=False)#.encode('utf-8')

        xlsx_2 = to_excel(entity)

        now = datetime.now(pytz.timezone('Asia/Tbilisi')).strftime('%d_%m_%Y_%H_%M_%S')

        # Button to download CSV
        st.download_button(label = "Download EU Excel", data=xlsx_2, file_name=f"EU_restrictions_{now}.xlsx", mime='application/vnd.ms-excel',)

    else:
        st.write("Failed to retrieve the page. Please check the URL.")


    

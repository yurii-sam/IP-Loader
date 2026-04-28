import concurrent.futures
from bs4 import BeautifulSoup
from .aspnet import AspNetNavigator

VELOCITY_ROOT = "https://velocity.web.boeing.com/Intercim/pub"
VELOCITY_SEARCH_PAGE_URL = f"{VELOCITY_ROOT}/executionordersearch_custom.aspx?IsInPlanning=False"


class VelocityClient:
    def __init__(self, auth_session):
        # We store the authenticated SSO session here. It handles the cookie jar.
        self.session = auth_session

        # Base headers that won't change.
        # We DO NOT use session.headers.update() here so we remain thread-safe.
        self.base_headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Content-Type': 'application/x-www-form-urlencoded',
            'DNT': '1',
            'Host': 'velocity.web.boeing.com',
            'Origin': 'https://velocity.web.boeing.com',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0'
        }

    @staticmethod
    def _compute_crc(text):
        crc_table = []
        for n in range(256):
            c = n
            for _ in range(8):
                if c & 1:
                    c = 0xEDB88320 ^ (c >> 1)
                else:
                    c = c >> 1
            crc_table.append(c)

        crc = 0xFFFFFFFF
        for char in text:
            char_code = ord(char) & 0xFF
            crc = (crc >> 8) ^ crc_table[(crc ^ char_code) & 0xFF]

        return (crc ^ 0xFFFFFFFF) & 0xFFFFFFFF

    def search_order(self, target_order_id, target_ln='1343'):
        print(f"[{target_order_id}] Initiating search...")

        # Initialize the wrapper. It will use the session's cookie jar.
        nav = AspNetNavigator(session=self.session, url=VELOCITY_SEARCH_PAGE_URL)
        soup = nav.load_initial_page()

        page_guid = soup.find('input', {'name': 'PageGuid'})
        app_root = soup.find('input', {'name': 'AppRoot'})

        evaluated_xml = (
            f'<search><expression>OrderObjectDS.Id<op type="eq"/>{target_order_id}</expression>'
            f'<op type="and"/><expression>OrderObjectDS.Suffix<op type="eq"/>{target_ln}</expression>'
            f'<op type="and"/><expression>OrderObjectDS.PartId<op type="eq"/>*</expression>'
            f'<op type="and"/><expression>OrderObjectDS.PartRevision<op type="eq"/>*</expression>'
            f'<op type="and"/><expression>OrderObjectDS.UserAttribute22<op type="eq"/>*</expression>'
            f'<op type="and"/><expression>OrderObjectDS.Status<op type="eq"/>*</expression></search>'
        )

        payload = {
            'AppRoot': app_root.get('value', '/Intercim') if app_root else '/Intercim',
            'PageGuid': page_guid.get('value', '') if page_guid else '',
            'txtOrderID': target_order_id,
            'lbUnit': target_ln,
            'txtSuffix': '',
            'ddlStatus': '',
            'txtPartId': '',
            'ddlDelmiaGroupCode': '',
            'ddlDelmiaGroupCode_Cddl_ClientState': ':::',
            'ddProdRepairStation': 'P',
            'theSearch': evaluated_xml,
            'theSearchXml': '<search> <expression>OrderObjectDS.Id<op type="eq" />%ID:txtOrderID%</expression> <op type="and" /> <expression>OrderObjectDS.Suffix<op type="eq" />%ID:lbUnit%</expression> <op type="and" /> <expression>OrderObjectDS.PartId<op type="eq" />%ID:txtPartId%</expression> <op type="and" /> <expression>OrderObjectDS.PartRevision<op type="eq" />%ID:txtPartRev%</expression> <op type="and" /> <expression>OrderObjectDS.UserAttribute22<op type="eq" />%ID:ddlDelmiaGroupCode%</expression> <op type="and" /> <expression>OrderObjectDS.Status<op type="eq" />%ID:ddlStatus%</expression> </search>',
            'CRC': str(self._compute_crc(evaluated_xml)),
            'btnFind': '  Find  ',
            'tbHDNUserName': '',
            'txtSaveThisSearch': '',
            'ddlSelectSearch': '',
            'ddlProdLocation': '',
            'ddICS': '',
            'txtPartRev': '',
            'ddlSuperindent$hdnLstItems': '',
            'lbGenerals$hdnLstItems': '',
            'lbTeam$hdnLstItems': '',
            'hdnPrintState': '',
            'hiddenInputToUpdateATBuffer_CommonToolkitScripts': '0'
        }

        # Fire postback. The wrapper handles the ViewState injection.
        try:
            return nav.do_postback(event_target='', extra_form_data=payload)
        except Exception as e:
            print(f"[{target_order_id}] Search failed: {e}")
            return None

    def get_print_url(self, search_soup):
        table = search_soup.find('table', id='dgrOrderList')
        if not table:
            return None

        link = table.find('a', id=lambda x: x and x.startswith('dgrOrderList_ctl') and x.endswith('hlnkOrder'))
        if not link or not link.get('href'):
            return None

        href = link.get('href')
        raw_url = f"{VELOCITY_ROOT}/{href}" if not href.startswith('/') else f"{VELOCITY_ROOT}{href}"
        return raw_url.replace('executionorder.aspx', 'Print_SOI_New.aspx')

    def download_print(self, order_id, print_url):
        print(f"[{order_id}] Extracting print payload...")

        req_headers = self.base_headers.copy()
        req_headers['Referer'] = VELOCITY_SEARCH_PAGE_URL

        response = self.session.get(print_url, headers=req_headers)
        soup = BeautifulSoup(response.text, 'html.parser')

        print_payload = {}
        for tag in soup.find_all(['input', 'select', 'textarea']):
            name = tag.get('name')
            if not name: continue

            tag_type = tag.get('type', '').lower()
            if tag_type in ['submit', 'button', 'image']: continue

            if tag_type in ['checkbox', 'radio']:
                print_payload[name] = 'on'
                continue

            if tag.name == 'select':
                selected = tag.find('option', selected=True)
                print_payload[name] = selected.get('value', '') if selected else ''
            else:
                print_payload[name] = tag.get('value', '')

        print_payload['chkAsBuiltData'] = 'on'
        print_payload['chkSelectAllOpers'] = 'on'
        print_payload['x'] = '18'
        print_payload['y'] = '11'
        print_payload['__DEFAULT_BUTTON'] = ''

        print(f"[{order_id}] Riding redirect to processor...")

        # Update referer to the print page itself before POSTing
        req_headers['Referer'] = print_url
        processor_response = self.session.post(print_url, headers=req_headers, data=print_payload, allow_redirects=True)

        if "Print_Processor.aspx" in processor_response.url:
            output_file = f"SOI_{order_id}.html"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(processor_response.text)
            print(f"[{order_id}] Success. Saved to {output_file}")
            return True
        else:
            print(f"[{order_id}] Redirect failed. Stopped at {processor_response.url}")
            return False

    def process_order(self, order_id, ln='1343'):
        """The main orchestration method for a single order."""
        try:
            search_soup = self.search_order(order_id, ln)
            if not search_soup: return False

            print_url = self.get_print_url(search_soup)
            if not print_url:
                print(f"[{order_id}] Could not find context URL in search results.")
                return False

            return self.download_print(order_id, print_url)
        except Exception as e:
            print(f"[{order_id}] Unhandled crash: {e}")
            return False


# --- HOW TO RUN IT IN YOUR MAIN BLOCK ---
# if __name__ == "__main__":
#     from gas_auth import get_gas_authentication
#
#     # 1. Do the heavy SSO auth exactly ONCE
#     print("Obtaining authenticated session via AutoSignOn...")
#     auth_result = get_gas_authentication(auth_type="AutoSignOn", app_url=VELOCITY_SEARCH_PAGE_URL, force=True)
#     master_session = auth_result.session
#     print("Authenticated session obtained.")
#
#     # 2. Spin up the client wrapper
#     client = VelocityClient(master_session)
#
#     # 3. Define your orders
#     orders_to_scrape = ['CAF20AFBB5304', 'SOME_OTHER_ID', 'AND_ANOTHER_ONE']
#
#     # 4. Thread pool execution
#     # Keep max_workers low (like 3 to 5) so you don't accidentally DDoS the legacy server
#     with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
#         # Map the process_order function to your list of IDs
#         # The client naturally handles the state isolation per thread
#         futures = {executor.submit(client.process_order, order_id): order_id for order_id in orders_to_scrape}
#
#         for future in concurrent.futures.as_completed(futures):
#             order = futures[future]
#             try:
#                 result = future.result()
#             except Exception as exc:
#                 print(f"{order} generated an exception: {exc}")
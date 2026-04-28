from bs4 import BeautifulSoup


class AspNetNavigator:
    def __init__(self, session, url):
        self.session = session
        self.url = url
        self.viewstate = ''
        self.generator = ''
        self.validation = ''
        self.current_soup = None

    def _extract_state_from_soup(self, soup):
        vs = soup.find('input', {'id': '__VIEWSTATE'})
        vsg = soup.find('input', {'id': '__VIEWSTATEGENERATOR'})
        ev = soup.find('input', {'id': '__EVENTVALIDATION'})

        self.viewstate = vs.get('value', '') if vs else self.viewstate
        self.generator = vsg.get('value', '') if vsg else self.generator
        self.validation = ev.get('value', '') if ev else self.validation

    def _parse_aspnet_ajax(self, response_text):
        parsed_data = {}
        index = 0

        while index < len(response_text):
            pipe_pos = response_text.find('|', index)
            if pipe_pos == -1: break
            try:
                length = int(response_text[index:pipe_pos])
            except ValueError:
                break

            index = pipe_pos + 1

            pipe_pos = response_text.find('|', index)
            chunk_type = response_text[index:pipe_pos]
            index = pipe_pos + 1

            pipe_pos = response_text.find('|', index)
            chunk_id = response_text[index:pipe_pos]
            index = pipe_pos + 1

            content = response_text[index:index + length]
            parsed_data[chunk_id] = {'type': chunk_type, 'content': content}
            index = index + length + 1

        return parsed_data

    def load_initial_page(self):
        """Hits the URL for the first time to grab the Holy Trinity."""
        response = self.session.get(self.url)
        response.raise_for_status()
        self.current_soup = BeautifulSoup(response.text, 'html.parser')
        self._extract_state_from_soup(self.current_soup)
        return self.current_soup

    def do_postback(self, event_target, event_argument='', extra_form_data=None, is_ajax=False):
        """
        Simulates a postback click.
        extra_form_data is a dict for things like dropdown selections or text inputs.
        """
        payload = {
            '__VIEWSTATE': self.viewstate,
            '__VIEWSTATEGENERATOR': self.generator,
            '__EVENTVALIDATION': self.validation,
            '__EVENTTARGET': event_target,
            '__EVENTARGUMENT': event_argument
        }

        if extra_form_data:
            payload.update(extra_form_data)

        headers = {}
        if is_ajax:
            headers['X-MicrosoftAjax'] = 'Delta=true'

        response = self.session.post(self.url, data=payload, headers=headers)
        response.raise_for_status()

        if is_ajax:
            # Handle the pipe nightmare and update state
            parsed_data = self._parse_aspnet_ajax(response.text)

            if '__VIEWSTATE' in parsed_data:
                self.viewstate = parsed_data['__VIEWSTATE']['content']
            if '__VIEWSTATEGENERATOR' in parsed_data:
                self.generator = parsed_data['__VIEWSTATEGENERATOR']['content']
            if '__EVENTVALIDATION' in parsed_data:
                self.validation = parsed_data['__EVENTVALIDATION']['content']

            return parsed_data
        else:
            # Handle a standard full-page reload
            self.current_soup = BeautifulSoup(response.text, 'html.parser')
            self._extract_state_from_soup(self.current_soup)
            return self.current_soup
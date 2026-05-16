import requests
import time

class HeroSMS:
    def __init__(self, api_key):
        self.api_key = api_key
        self.stub_url = "https://hero-sms.com/stubs/handler_api.php"
        self.rest_url = "https://hero-sms.com/api/v1"

    def stub_request(self, action, params=None):
        if params is None: params = {}
        params['api_key'] = self.api_key
        params['action'] = action
        try:
            response = requests.get(self.stub_url, params=params, timeout=10)
            if response.status_code == 200:
                try: return response.json()
                except: return response.text
        except Exception: pass
        return None

    def fetch_base_data(self):
        countries = self.stub_request("getCountries")
        services_data = self.stub_request("getServicesList")
        return countries, services_data

    def search_item(self, data_list, query, mode="country"):
        query = str(query).lower().strip()
        results = []
        if mode == "country" and isinstance(data_list, dict):
            # If getCountries returns a dict instead of list, we handle both just in case
            data_list = [v for k, v in data_list.items()] if isinstance(data_list, dict) else data_list
        if mode == "country" and isinstance(data_list, list):
            for item in data_list:
                if str(item.get('id', '')) == query: return [{"id": item.get('id'), "name": f"{item.get('chn', '')}"}]
                chn, eng = str(item.get('chn', '')), str(item.get('eng', '')).lower()
                if query in chn or query in eng:
                    results.append({"id": item.get('id'), "name": f"{chn} ({item.get('eng', eng)})"})
        elif mode == "service" and isinstance(data_list, dict):
            for item in data_list.get("services", []):
                if str(item.get('code', '')).lower() == query: return [{"code": item.get('code'), "name": item.get('name')}]
                code, name = str(item.get('code', '')).lower(), str(item.get('name', '')).lower()
                if query in code or query in name:
                    results.append({"code": item.get('code'), "name": item.get('name')})
        elif mode == "service" and isinstance(data_list, list):
             for item in data_list:
                 if str(item.get('code', '')).lower() == query: return [{"code": item.get('code'), "name": item.get('name')}]
                 code, name = str(item.get('code', '')).lower(), str(item.get('name', '')).lower()
                 if query in code or query in name:
                     results.append({"code": item.get('code'), "name": item.get('name')})           
        return results

    def get_latest_offers(self, c_id, s_code):
        url = f"{self.rest_url}/activations/offers"
        headers = {"Authorization": f"ApiKey {self.api_key}", "Accept": "application/json"}
        params = {"api_key": self.api_key, "countries": c_id, "services": s_code}
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code == 401:
                headers.pop("Authorization", None)
                resp = requests.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                raw_content = data.get("data", data)
                target_node = None
                if isinstance(raw_content, dict):
                    s_dict = raw_content.get(s_code, {})
                    target_node = s_dict.get(str(c_id), {}) if isinstance(s_dict, dict) else {}
                    if not target_node or 'map' not in target_node:
                        for sk in raw_content.values():
                            if isinstance(sk, dict):
                                for ck in sk.values():
                                    if isinstance(ck, dict) and 'map' in ck:
                                        target_node = ck; break
                offers_map = target_node.get("map", {}) if target_node else {}
                if not offers_map: return None
                sorted_prices = sorted(offers_map.keys(), key=lambda x: float(x))
                parsed_offers = []
                prev_cum = 0
                for p_str in sorted_prices:
                    cum = offers_map[p_str]
                    exact = cum - prev_cum
                    if exact > 0: parsed_offers.append({"price": p_str, "count": exact})
                    prev_cum = cum
                return sorted(parsed_offers, key=lambda x: float(x["price"]), reverse=True)
        except Exception: pass
        return None

    def get_real_cost(self, order_id):
        try:
            active_data = self.stub_request("getActiveActivations")
            if isinstance(active_data, dict) and "activeActivations" in active_data:
                for act in active_data["activeActivations"]:
                    if str(act.get("activationId")) == str(order_id): return float(act.get("activationCost", 0))
        except Exception: pass
        return None

    def get_balance(self):
        res = self.stub_request("getBalance")
        if isinstance(res, str) and res.startswith("ACCESS_BALANCE"):
            return res.split(":")[1]
        return "Unknown"

    def get_number(self, service, country, max_price):
        try: target_price = float(max_price)
        except: target_price = None

        countries, services_data = self.fetch_base_data()
        
        c_id = country
        if str(country).lower() not in ["any", "0"]:
            c_res = self.search_item(countries, country, "country")
            if c_res: c_id = c_res[0]["id"]
            else: c_id = str(country)
            
        s_code = service
        s_res = self.search_item(services_data, service, "service")
        if s_res: s_code = s_res[0]["code"]
        else: s_code = str(service)

        purchase_price = None
        if target_price:
            if str(c_id).lower() not in ["any", "0"]:
                offers = self.get_latest_offers(str(c_id), s_code)
                if offers:
                    valid_offers = [o for o in offers if float(o["price"]) <= target_price]
                    if valid_offers:
                        purchase_price = valid_offers[0]["price"]

        req_params = {"service": s_code, "country": c_id}
        if purchase_price is not None:
            req_params["maxPrice"] = str(purchase_price)
        elif target_price is not None:
            req_params["maxPrice"] = str(target_price)

        res = self.stub_request("getNumber", req_params)
        
        if isinstance(res, str) and res.startswith("ACCESS_NUMBER"):
            _, order_id, phone = res.split(":")
            if target_price:
                real_cost = self.get_real_cost(order_id)
                if real_cost and real_cost > target_price:
                    self.set_status(order_id, 8)
                    return None, f"价格保护生效：实际价格 ${real_cost} 高于设定保护价 ${target_price}"
            return order_id, phone
            
        return None, res

    def get_status(self, order_id):
        return self.stub_request("getStatus", {"id": order_id})

    def set_status(self, order_id, status):
        return self.stub_request("setStatus", {"id": order_id, "status": status})

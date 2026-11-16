"""API tests (no browser):
1 create / get / join; the host gets the password back, guests don't; default title in the caller's language
2 meeting password: required, wrong, right, and locked after 10 wrong tries
3 host-only actions (mute, end) need the host key; ending a meeting closes it for everyone
4 no database: another instance with the same secret (= a restart) still knows the meeting and the host;
  an instance with a different secret does not accept the host key
5 creation passcode and the per-IP rate limit
6 bad input: malformed IDs, empty names"""
import asyncio
import httpx

A, B, P, X = "http://127.0.0.1:8000", "http://127.0.0.1:8001", "http://127.0.0.1:8002", "http://127.0.0.1:8003"


async def main():
    async with httpx.AsyncClient(timeout=20) as c:
        # 1
        r = await c.post(f"{A}/api/rooms", json={"nickname": "Ana", "room_pass": "s3cret"}, headers={"X-Lang": "es"})
        assert r.status_code == 200, r.text
        d = r.json(); code, key = d["room"]["code"], d["owner_key"]
        assert len(code) == 9 and code[0] != "0" and d["role"] == "owner" and d["token"] and d["room"]["password"] == "s3cret"
        assert d["room"]["title"] == "Reunión de Ana", d["room"]["title"]
        g = (await c.get(f"{A}/api/rooms/{code}")).json()
        assert g["has_password"] and "password" not in g and g["owner_nickname"] == "Ana"
        assert (await c.get(f"{A}/api/rooms/{code}", headers={"X-Owner-Key": key})).json()["password"] == "s3cret"
        r = await c.post(f"{A}/api/rooms/{code.replace('', ' ').strip()}/join", json={"nickname": "Bo", "room_pass": "s3cret"})
        assert r.status_code == 200 and r.json()["role"] == "member" and "password" not in r.json()["room"], r.text
        r = await c.post(f"{A}/api/rooms/{code}/join", json={"nickname": "Ana", "owner_key": key})
        assert r.status_code == 200 and r.json()["role"] == "owner"   # the host needs no password
        print("1 create / get / join; host-only password; localized default title")

        # 2
        r = await c.post(f"{A}/api/rooms/{code}/join", json={"nickname": "Bo"}, headers={"X-Lang": "zh-CN"})
        assert r.status_code == 403 and "密码" in r.json()["detail"], r.text
        for i in range(10):
            r = await c.post(f"{A}/api/rooms/{code}/join", json={"nickname": "Bo", "room_pass": f"nope{i}"})
            assert r.status_code == 403, r.text
        r = await c.post(f"{A}/api/rooms/{code}/join", json={"nickname": "Bo", "room_pass": "s3cret"})
        assert r.status_code == 429, r.text   # locked for this IP and meeting
        print("2 meeting password: required / wrong / locked after 10 wrong tries")

        # 3
        assert (await c.post(f"{A}/api/rooms/{code}/mute", json={"owner_key": "nope"})).status_code == 403
        r = await c.post(f"{A}/api/rooms/{code}/mute", json={"owner_key": key, "mute": True})
        assert r.status_code == 200 and r.json()["count"] == 0, r.text   # nobody connected yet
        assert (await c.post(f"{A}/api/rooms/{code}/end", json={"owner_key": "nope"})).status_code == 403
        r2 = (await c.post(f"{A}/api/rooms", json={"nickname": "Cy"})).json()
        code2, key2 = r2["room"]["code"], r2["owner_key"]
        assert not r2["room"]["has_password"] and r2["room"]["password"] is None
        assert (await c.post(f"{A}/api/rooms/{code2}/end", json={"owner_key": key2})).status_code == 200
        for base in (A, B):
            assert (await c.get(f"{base}/api/rooms/{code2}")).status_code == 404
        assert (await c.post(f"{A}/api/rooms/{code2}/join", json={"nickname": "Bo"})).status_code == 404
        print("3 mute and end need the host key; an ended meeting is gone everywhere")

        # 4
        g = (await c.get(f"{B}/api/rooms/{code}", headers={"X-Owner-Key": key})).json()
        assert g["title"] == "Reunión de Ana" and g["has_password"] and g["password"] is None   # plain password is not kept by other processes
        r = await c.post(f"{B}/api/rooms/{code}/join", json={"nickname": "Dee", "room_pass": "s3cret"})
        assert r.status_code == 200, r.text
        r = await c.post(f"{B}/api/rooms/{code}/join", json={"nickname": "Dee", "room_pass": "wrong"})
        assert r.status_code == 403, r.text
        assert (await c.post(f"{B}/api/rooms/{code}/join", json={"nickname": "Ana", "owner_key": key})).json()["role"] == "owner"
        # an instance with another secret can verify neither the host key nor the password
        assert (await c.post(f"{X}/api/rooms/{code}/join", json={"nickname": "Ana", "owner_key": key, "room_pass": "s3cret"})).status_code == 403
        assert (await c.post(f"{X}/api/rooms/{code}/end", json={"owner_key": key})).status_code == 403
        print("4 no database: a restarted instance still knows the meeting, its password and its host; another secret does not")

        # 5
        assert (await c.get(f"{P}/api/config")).json()["require_passcode"] is True
        r = await c.post(f"{P}/api/rooms", json={"nickname": "Ed"}); assert r.status_code == 403, r.text
        made = []
        for i in range(3):
            r = await c.post(f"{P}/api/rooms", json={"nickname": "Ed", "passcode": "letmein"}); assert r.status_code == 200, r.text
            made.append(r.json())
        r = await c.post(f"{P}/api/rooms", json={"nickname": "Ed", "passcode": "letmein"}, headers={"X-Lang": "de"})
        assert r.status_code == 429 and "(Limit 3)" in r.json()["detail"], r.text
        for m in made:
            await c.post(f"{P}/api/rooms/{m['room']['code']}/end", json={"owner_key": m["owner_key"]})
        print("5 creation passcode; per-IP rate limit")

        # 6
        for bad in ("12345", "1234567890", "abcdefghi"):
            assert (await c.get(f"{A}/api/rooms/{bad}")).status_code == 404
        assert (await c.post(f"{A}/api/rooms", json={"nickname": "  "})).status_code == 400
        assert (await c.post(f"{A}/api/rooms", json={"nickname": ""})).status_code == 422
        await c.post(f"{A}/api/rooms/{code}/end", json={"owner_key": key})
        print("6 malformed meeting IDs and empty names are refused")
    print("API OK")

asyncio.run(main())

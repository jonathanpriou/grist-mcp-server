from fastmcp import FastMCP
import httpx

mcp = FastMCP("Grist Fetcher")

@mcp.tool
async def fetch_grist_records(
    url: str,
    bearer_token: str,
    limit: int = 5
) -> dict:
    """
    Appelle une API Grist et retourne les records aplatis.

    Args:
        url: URL complète de la table Grist (sans ?limit)
        bearer_token: Token Bearer pour l authentification
        limit: Nombre de records a recuperer (defaut 5)
    """
    full_url = f"{url}?limit={limit}"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            full_url,
            headers={"Authorization": f"Bearer {bearer_token}"}
        )
        response.raise_for_status()
        data = response.json()

    records = data.get("records", [])
    if not records:
        return {"records": [], "csv": "", "columns": []}

    flat_records = []
    for record in records:
        row = {"id": record.get("id")}
        fields = record.get("fields", {})
        for key, value in fields.items():
            clean_key = key.replace(" ", "_").replace("-", "_")
            if isinstance(value, list) and len(value) > 0 and value[0] == "L":
                row[clean_key] = "|".join(str(v) for v in value[1:])
            elif value is None:
                row[clean_key] = ""
            else:
                row[clean_key] = value
        flat_records.append(row)

    columns = list(flat_records[0].keys()) if flat_records else []
    csv_lines = [",".join(columns)]
    for row in flat_records:
        csv_lines.append(",".join(
            f'"{str(row.get(col, "")).replace(chr(34), chr(39))}"'
            for col in columns
        ))

    return {
        "records": flat_records,
        "csv": "\n".join(csv_lines),
        "columns": columns,
        "total_fetched": len(flat_records)
    }


@mcp.tool
async def update_huwise_dataset(
    grist_url: str,
    grist_token: str,
    huwise_dataset_uid: str,
    huwise_token: str,
    huwise_domain: str = "https://poc-gps.trial.opendatasoft.com",
    max_records: int = 100
) -> dict:
    """
    Récupère les records Grist via pagination et met à jour le dataset Huwise.

    Args:
        grist_url: URL complète de la table Grist (sans ?limit ni ?offset)
        grist_token: Bearer token Grist
        huwise_dataset_uid: UID du dataset Huwise (ex: da_xxxxx)
        huwise_token: Token d authentification Huwise
        huwise_domain: Domaine du portail Huwise
        max_records: Nombre maximum de records à charger (defaut 100)
    """
    all_records = []
    offset = 0
    limit = 20

    async with httpx.AsyncClient(timeout=60) as client:
        while len(all_records) < max_records:
            remaining = max_records - len(all_records)
            page_limit = min(limit, remaining)

            response = await client.get(
                f"{grist_url}?limit={page_limit}&offset={offset}",
                headers={"Authorization": f"Bearer {grist_token}"}
            )
            response.raise_for_status()
            data = response.json()

            records = data.get("records", [])
            if not records:
                break

            for record in records:
                row = {"id": record.get("id")}
                fields = record.get("fields", {})
                for key, value in fields.items():
                    clean_key = key.replace(" ", "_").replace("-", "_")
                    if isinstance(value, list) and len(value) > 0 and value[0] == "L":
                        row[clean_key] = "|".join(str(v) for v in value[1:])
                    elif value is None:
                        row[clean_key] = ""
                    else:
                        row[clean_key] = value
                all_records.append(row)

            if len(records) < page_limit:
                break

            offset += page_limit

    if not all_records:
        return {"success": False, "error": "Aucun record récupéré depuis Grist"}

    columns = list(all_records[0].keys())
    csv_lines = [",".join(columns)]
    for row in all_records:
        csv_lines.append(",".join(
            f'"{str(row.get(col, "")).replace(chr(34), chr(39))}"'
            for col in columns
        ))
    csv_content = "\n".join(csv_lines)

 filename = f"{huwise_dataset_uid}-full.csv"
async with httpx.AsyncClient(timeout=60) as client:
    response = await client.post(
        f"{huwise_domain}/api/management/v2/datasets/{huwise_dataset_uid}/files/",
        headers={"Authorization": f"Apikey {huwise_token}"},
        files={"file": (filename, csv_content.encode("utf-8"), "text/csv")}
    )
    response.raise_for_status()
    file_data = response.json()
    file_uid = file_data.get("uid") or file_data.get("file_uid")

return {
    "success": True,
    "total_records": len(all_records),
    "columns": columns,
    "filename": filename,
    "file_uid": file_uid
}


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    mcp.run(transport="http", host="0.0.0.0", port=port)

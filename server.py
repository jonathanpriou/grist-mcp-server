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
        url: URL complete de la table Grist (sans ?limit)
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


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    mcp.run(transport="http", host="0.0.0.0", port=port)

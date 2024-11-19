from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, FileResponse
import pandas as pd
import matplotlib.pyplot as plt
import os
import zipfile
from io import BytesIO

app = FastAPI()

# Directory to save plots temporarily
PLOT_DIR = "plots"
os.makedirs(PLOT_DIR, exist_ok=True)


@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    """
    Endpoint to upload and process an Excel file.
    Validates file format and processes the data.
    """
    try:
        # Validate the file extension
        if not file.filename.endswith(('.xls', '.xlsx')):
            raise HTTPException(status_code=400, detail="Invalid file format. Only Excel files are allowed.")
        
        # Read the Excel file into a DataFrame
        df = pd.read_excel(file.file)

        # Handle invalid values (NaN, inf, -inf)
        df.fillna(0, inplace=True)
        df.replace([float('inf'), float('-inf')], 0, inplace=True)

        # Convert the processed DataFrame to a JSON-compatible format
        data = df.to_dict(orient='records')

        return JSONResponse(content={
            "message": "File processed successfully",
            "num_rows": len(df),
            "data": data
        })

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"An error occurred while processing the file: {str(e)}")


@app.post("/generate-plots/")
async def generate_all_plots(file: UploadFile = File(...)):
    """
    Automatically generates all plot types (line, bar, scatter, histogram) for numeric columns in the uploaded Excel file.
    """
    try:
        # Validate the file extension
        if not file.filename.endswith(('.xls', '.xlsx')):
            raise HTTPException(status_code=400, detail="Invalid file format. Only Excel files are allowed.")
        
        # Read the Excel file into a DataFrame
        df = pd.read_excel(file.file)

        # Handle invalid values (NaN, inf, -inf)
        df.fillna(0, inplace=True)
        df.replace([float('inf'), float('-inf')], 0, inplace=True)

        # Select numeric columns for plotting
        numeric_columns = df.select_dtypes(include=['number']).columns
        if numeric_columns.empty:
            raise HTTPException(status_code=400, detail="No numeric columns found to plot.")

        plot_types = ["line", "bar", "scatter", "hist"]
        plot_paths = []

        # Generate plots for each column and type
        for column in numeric_columns:
            for plot_type in plot_types:
                plt.figure()

                # Generate the plot based on the type
                if plot_type == "line":
                    df[column].plot(kind="line", title=f"Line Plot for {column}")
                elif plot_type == "bar":
                    df[column].plot(kind="bar", title=f"Bar Plot for {column}")
                elif plot_type == "scatter":
                    if len(numeric_columns) < 2:
                        continue  # Skip scatter plot if there's only one numeric column
                    df.plot.scatter(x=numeric_columns[0], y=column, title=f"Scatter Plot for {column}")
                elif plot_type == "hist":
                    df[column].plot(kind="hist", title=f"Histogram for {column}", bins=10)

                # Save the plot
                plot_path = os.path.join(PLOT_DIR, f"{column}_{plot_type}.png")
                plt.savefig(plot_path)
                plt.close()
                plot_paths.append(plot_path)

        return JSONResponse(content={
            "message": "Plots generated successfully",
            "plots": [
                f"http://127.0.0.1:8000/download-plot/?plot_name={os.path.basename(path)}"
                for path in plot_paths
            ],
            "download_all": "http://127.0.0.1:8000/download-all-plots/"
        })

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"An error occurred while creating plots: {str(e)}")


@app.get("/download-plot/")
async def download_plot(plot_name: str):
    """
    Endpoint to download a specific plot by name.
    """
    plot_path = os.path.join(PLOT_DIR, plot_name)
    if os.path.exists(plot_path):
        return FileResponse(plot_path, media_type="image/png", filename=plot_name)
    else:
        raise HTTPException(status_code=404, detail="Plot not found")


@app.get("/download-all-plots/")
async def download_all_plots():
    """
    Endpoint to download all generated plots as a zip file.
    """
    try:
        # Create a BytesIO buffer for the zip file
        buffer = BytesIO()

        with zipfile.ZipFile(buffer, "w") as zf:
            for filename in os.listdir(PLOT_DIR):
                file_path = os.path.join(PLOT_DIR, filename)
                zf.write(file_path, arcname=filename)

        # Reset buffer position to the beginning
        buffer.seek(0)

        return FileResponse(
            buffer,
            media_type="application/zip",
            filename="all_plots.zip"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while creating the zip file: {str(e)}")

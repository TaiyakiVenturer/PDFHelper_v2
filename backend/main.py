def main():
    from backend.services.mineru import MinerUCLIWrapper

    def on_progress(percent: float, message: str) -> None:
        print(f"[{percent:6.2f}%] {message}")

    wrapper = MinerUCLIWrapper(
        output_dir="D:/Thomas/Desktop/College_Codes/SchoolProject/PDFHelper/data/mineru_outputs",
        on_progress=on_progress,
        verbose=True,
    )

    result = wrapper.process(
        pdf_path="D:/Thomas/Desktop/College_Codes/SchoolProject/PDFHelper/data/pdfs/SG90.pdf",
        method="auto",   # auto/txt/ocr
        lang="en",
        formula=True,
        table=True,
        start=None,      # 或 1
        end=None,        # 或 7
    )

    print("success:", result.success)
    print("output_path:", result.output_path)
    print("markdown:", result.output_file_paths.markdown)
    print("json:", result.output_file_paths.json)
    print("images:", len(result.output_file_paths.images))
    print("returncode:", result.returncode)
    print("error:", result.error)
    print("time:", result.processing_time)


if __name__ == "__main__":
    main()

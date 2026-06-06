import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ImageViewer } from "@/components/invoices/viewers/image-viewer";

describe("ImageViewer", () => {
  it("renders img with correct src", () => {
    render(<ImageViewer fileUrl="/image.png" filename="image.png" />);

    const image = screen.getByRole("img", { name: /Vorschau image\.png/i });
    expect(image).toHaveAttribute("src", "/image.png");
  });

  it("zoom controls work", () => {
    render(<ImageViewer fileUrl="/image.png" filename="image.png" />);

    const image = screen.getByRole("img", { name: /Vorschau image\.png/i });
    fireEvent.load(image);

    expect(screen.getByText("100%")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Vergrößern" }));
    expect(screen.getByText("125%")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Zurücksetzen" }));
    expect(screen.getByText("100%")).toBeInTheDocument();
  });
});

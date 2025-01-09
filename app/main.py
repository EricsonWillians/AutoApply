"""
Main application module for AutoApply.

This module serves as the entry point for the AutoApply application,
providing a command-line interface and orchestrating the various
components of the system.

File location: app/main.py
"""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from app.core.form_filler import form_filler
from app.core.pdf_parser import create_profile_from_pdf
from app.core.verification import form_verification
from app.utils.config import settings
from app.utils.logging import LoggerMixin, get_logger

# Initialize application
app = typer.Typer(
    name="autoapply",
    help="Automate job applications using LinkedIn profile data",
    add_completion=False,
)

console = Console()
logger = get_logger(__name__)


class ApplicationManager(LoggerMixin):
    """Manages the application workflow and orchestrates components."""

    def __init__(self) -> None:
        """Initialize the application manager."""
        super().__init__()
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        settings.ensure_directories()

    async def extract_profile(self, pdf_path: Path) -> None:
        """
        Extract profile data from LinkedIn PDF export.

        Args:
            pdf_path: Path to the LinkedIn profile PDF.
        """
        try:
            self.log_operation_start("profile extraction", pdf_path=str(pdf_path))

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task(description="Extracting profile data...", total=None)

                profile = create_profile_from_pdf(pdf_path)

            console.print("\n✓ Profile data extracted successfully", style="bold green")
            self.log_operation_end("profile extraction")

        except Exception as e:
            self.log_error(e, "profile extraction")
            console.print(f"\n✗ Error extracting profile: {str(e)}", style="bold red")
            raise typer.Exit(1)

    async def apply_to_job(
        self,
        job_url: str,
        resume_path: Optional[Path] = None,
        confidence_threshold: float = 0.8,
    ) -> None:
        """
        Apply to a job using extracted profile data.

        Args:
            job_url: URL of the job application.
            resume_path: Optional path to resume file.
            confidence_threshold: Minimum confidence score for automatic approval.
        """
        try:
            self.log_operation_start("job application", job_url=job_url)

            # Load profile data
            profile_path = settings.data_dir / "user_profile.json"
            if not profile_path.exists():
                raise FileNotFoundError(
                    "Profile data not found. Please extract your profile first."
                )

            profile = LinkedInProfile.from_json(profile_path)

            # Initialize form filler
            await form_filler.initialize(profile.dict())

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                # Navigate to job application
                task = progress.add_task(
                    description="Navigating to job application...", total=None
                )
                await form_filler.navigate_to_form(job_url)

                # Detect form fields
                progress.update(task, description="Detecting form fields...")
                fields = await form_filler.detect_form_fields()

                # Fill form fields
                progress.update(task, description="Filling form fields...")
                filled_fields = await form_filler.fill_form(fields, resume_path)

                # Verify form data
                progress.update(task, description="Awaiting verification...")
                result = await form_verification.verify_form_data(
                    form_filler.page, filled_fields, confidence_threshold
                )

                if result.approved:
                    # Submit form
                    progress.update(task, description="Submitting application...")
                    response = await form_filler.submit_form()

                    if response and response.ok:
                        console.print(
                            "\n✓ Application submitted successfully", style="bold green"
                        )
                    else:
                        console.print(
                            "\n⚠ Application submitted but response indicates potential issues",
                            style="bold yellow",
                        )
                else:
                    console.print(
                        "\n✗ Application cancelled during verification",
                        style="bold red",
                    )

            self.log_operation_end("job application")

        except Exception as e:
            self.log_error(e, "job application")
            console.print(f"\n✗ Error during application: {str(e)}", style="bold red")
            raise typer.Exit(1)

        finally:
            # Clean up resources
            await form_filler.cleanup()


# Initialize application manager
app_manager = ApplicationManager()


@app.command()
def extract(
    pdf_path: Path = typer.Argument(
        ...,
        help="Path to the LinkedIn profile PDF export",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    )
) -> None:
    """Extract profile data from LinkedIn PDF export."""
    asyncio.run(app_manager.extract_profile(pdf_path))


@app.command()
def apply(
    job_url: str = typer.Argument(..., help="URL of the job application form"),
    resume: Optional[Path] = typer.Option(
        None,
        "--resume",
        "-r",
        help="Path to resume file (PDF or DOCX)",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    ),
    confidence: float = typer.Option(
        0.8,
        "--confidence",
        "-c",
        help="Minimum confidence threshold for automatic approval",
        min=0.0,
        max=1.0,
    ),
) -> None:
    """Apply to a job using extracted profile data."""
    asyncio.run(app_manager.apply_to_job(job_url, resume, confidence))


@app.callback()
def callback() -> None:
    """AutoApply - Automated Job Application Tool."""
    try:
        # Validate environment
        if not settings.validate_paths():
            raise typer.Exit("Invalid application configuration")
    except Exception as e:
        logger.error("Startup error", error=str(e))
        raise typer.Exit(1)


if __name__ == "__main__":
    app()

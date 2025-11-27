import settings
import click
import asyncio

from utils import async_click
from core.core import Repo2PipeCore


@click.command()
@click.option("--type", default="gitlab", help="CI/CD pipline type")
@click.option("-o", "--output", default=".", help="Путь к директории, куда сохранить результат",)
@click.argument("repository")
@click.argument("branch", default="master")
@async_click
async def main(repository: str, branch: str, type: str, output: str = "./"):
    click.echo(settings.LOGO + "\n")

    repo2pipe = Repo2PipeCore(branch)
    result = await repo2pipe.create_pipline(
        repository=repository,
        branch=branch,
        pipeline_type=type,
    )

    ci_type = type

    template = result.ci_templates.get(ci_type)
    if not template:
        raise click.ClickException(
            f"CI type '{ci_type}' не найден в ci_templates. "
            f"Доступные: {list(result.ci_templates.keys())}"
        )

    click.echo(template)


    default_names = { "gitlab": ".gitlab-ci.yml", "jenkins": "Jenkinsfile" }
    filename = default_names.get(ci_type, f"{ci_type}_pipeline.txt")
    output += ("" if output[-1:] == "/" else "/") + filename 

    try:
        with open(output, "w", encoding="utf-8") as f:
            f.write(template)
    except OSError as e:
        click.echo(f"Не удалось сохранить YAML в файл '{output}': {e}", err=True)
    else:
        click.echo(f"YAML сохранён в файл: {output}", err=True)


if __name__ == "__main__":
    asyncio.run(main())
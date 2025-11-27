import click

class CLIException(BaseException):
    def __init__(self, *args, description:str = "Something happend..."):
        click.echo(description)
        super().__init__(*args)
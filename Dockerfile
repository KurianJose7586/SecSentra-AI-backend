# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /code

# Copy the requirements file first, to leverage Docker cache
COPY ./requirements.txt /code/requirements.txt

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy the rest of your application's code
COPY ./ /code/

# Expose the port the app runs on (FastAPI default is 8000, HF Spaces default is 7860)
# We will tell uvicorn to run on 7860.
EXPOSE 7860

# Run app.py when the container launches
# This is the command HF Spaces will run
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
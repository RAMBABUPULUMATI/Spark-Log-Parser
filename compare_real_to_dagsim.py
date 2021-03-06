#!/usr/bin/env python3

## Copyright 2017-2018 Eugenio Gianniti
##
## Licensed under the Apache License, Version 2.0 (the "License");
## you may not use this file except in compliance with the License.
## You may obtain a copy of the License at
##
##     http://www.apache.org/licenses/LICENSE-2.0
##
## Unless required by applicable law or agreed to in writing, software
## distributed under the License is distributed on an "AS IS" BASIS,
## WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
## See the License for the specific language governing permissions and
## limitations under the License.

import argparse
import csv
import os
import re
import sys

from collections import defaultdict
from pathlib import PurePath


def parse_dir_name (directory):
    experiment = query = None
    path = PurePath (directory)
    pieces = path.parts

    if len (pieces) >= 2:
        experiment = pieces[-2]
        query = pieces[-1]

    return experiment, query


def process_simulations (filename):
    with open (filename, newline = '') as csvfile:
        reader = csv.DictReader (csvfile)
        empirical = "Experiment" in reader.fieldnames

        if empirical:
            results = defaultdict (dict)
        else:
            results = defaultdict (lambda: defaultdict (dict))

        for row in reader:
            query = row["Query"]

            if empirical and query == row["Run"]:
                experiment = row["Experiment"]
                results[experiment][query] = float (row["SimAvg"])
            elif not empirical:
                model = int (row["ModelCores"])
                key = (int (row["SimCores"]), int (row["Datasize"]))
                results[key][query][model] = float (row["SimAvg"])

    return results, empirical


def process_summary (filename):
    cumsum = 0.
    count = 0

    with open (filename, newline = '') as csvfile:
        # Skip first line with application class
        try:
            next (csvfile)
        except StopIteration:
            pass

        reader = csv.DictReader (csvfile)

        try:
            for row in reader:
                cumsum += (float (row["applicationCompletionTime"]) -
                           float (row["applicationDeltaBeforeComputing"]))
                count += 1
        except KeyError as e:
            print ("warning: '{csv}' lacks key {key}"
                   .format (csv = filename, key = e),
                   file = sys.stderr)

    return cumsum / count


def parse_arguments (args = None):
    descr = "Build a CSV table comparing real data and empirical simulations"
    parser = argparse.ArgumentParser (description = descr)
    parser.add_argument ("--simulations", "-f",
                         help = "alternative simulations file")
    parser.add_argument ("root",
                         help = "directory with processed and simulated logs")
    return parser.parse_args (args)


def main (args):
    avg_R = defaultdict (dict)

    for directory, _, files in os.walk (args.root):
        if "failed" not in directory:
            for filename in files:
                full_path = os.path.join (directory, filename)

                if filename == "summary.csv":
                    experiment, query = parse_dir_name (directory)
                    result = process_summary (full_path)
                    avg_R[experiment][query] = result
                elif filename == "simulations.csv" and not args.simulations:
                    simulations_file = full_path

    sim_R, empirical = process_simulations (args.simulations or
                                            simulations_file)

    if empirical:
        errors = [
            {
                "Experiment": experiment,
                "Query": query,
                "Measured": real,
                "Simulated": sim_R[experiment][query],
                "Error[1]": (sim_R[experiment][query] - real) / real
            }
            for experiment, inner in avg_R.items ()
            for query, real in inner.items ()
        ]
    else:
        errors = list ()
        experiment_re = re.compile (
            "(?P<executors>\d+)_(?P<cpus>\d+)_\d+[mMgG]_(?P<datasize>\d+)")

        for experiment, inner in avg_R.items ():
            match = experiment_re.fullmatch (experiment)
            datasize = int (match["datasize"])
            cores = int (match["executors"]) * int (match["cpus"])

            for query, data in sim_R[(cores, datasize)].items ():
                real = inner[query]
                errors.extend ({
                    "Experiment": experiment,
                    "Query": query,
                    "Measured": real,
                    "Simulated": simulated,
                    "Error[1]": (simulated - real) / real,
                    "ModelCores": model
                } for model, simulated in data.items ())

    fields = ["Experiment", "Query", "Measured", "Simulated", "Error[1]"]

    if not empirical:
        fields.insert (2, "ModelCores")

    writer = csv.DictWriter (sys.stdout, fieldnames = fields)
    writer.writeheader ()
    writer.writerows (errors)


if __name__ == "__main__":
    args = parse_arguments ()
    main (args)

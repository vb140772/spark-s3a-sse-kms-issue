#!/bin/bash

set -e

case "$1" in
  master)
    exec /opt/spark/bin/spark-class org.apache.spark.deploy.master.Master
    ;;
  worker)
    exec /opt/spark/bin/spark-class org.apache.spark.deploy.worker.Worker spark://spark-master:7077
    ;;
  history)
    exec /opt/spark/bin/spark-class org.apache.spark.deploy.history.HistoryServer
    ;;
  *)
    echo "Usage: $0 {master|worker|history}"
    exit 1
    ;;
esac


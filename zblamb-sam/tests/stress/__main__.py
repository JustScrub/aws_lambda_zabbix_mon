from scripts.utility_scripts.generate_events import generate_events, get_functions
import sys, tempfile, json, subprocess

def print_usage():
    print("""
Usage: python3 -m zblamb-sam.tests.stress record_range functions_range reps [sam remote invoke arguments]
          record_range: list of 2 or 3 colon-delimited values start:stop[:step]
                start is the first number of records in the event
                end is the last number, if not overshot by step, exclusive!
                step is how much to increment the number of records in subsequent benchmarks
          functions_range: same format start:stop[:step] and meaning, but for number of functions inside a record
          reps: int, how many times to run the benchmark for each number of records and number of funcions
          sam remote invoke arguments: other arguments that will be passed to 'sam remote invoke'
                The Lambda name, ZBLambMetricStreamTransformLambda, is automatically filled in. 
                An event file, using --event-file, is automatically filled in as well
                You might want to specify the stack name using --stack-name
""")

if __name__ == "__main__":
    try:
        rec_range, func_range = list(map(
            lambda a: tuple(map(int, a.split(':'))),
            sys.argv[1:3]
        )) 
        reps = int(sys.argv[3])
    except:
        print_usage()
        exit(1)

    results = []
    fn_names = get_functions()
    sam_call = ["sam", "remote", "invoke", "--event-file", "<generated event>"] + sys.argv[4:] + ["ZBLambMetricStreamTransformLambda"]
    for n_records in range(*rec_range):
        for n_functions in range(*func_range):
            durs, errs = [], 0
            cont = True
            for rep in range(reps):
                evt = generate_events(fn_names,1,(n_records,n_records),(n_functions,n_functions))[0]
                with tempfile.NamedTemporaryFile() as f:
                    f.write(json.dumps(evt).encode())
                    if f.tell() > 6291456:
                        cont = False
                        break
                    sam_call[4] = f.name
                    r = subprocess.run(sam_call, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    so_lines = r.stdout.decode().splitlines()
                    dur = list(filter(lambda l: l.startswith("REPORT"), so_lines))[0]
                    dur = dur.split()
                    durs.append( float(dur[dur.index("Duration:")+1]) )
                    errs += int( "errorMessage" in so_lines[-1] or "errorType" in so_lines[-1])
            
            if durs:
                results.append(tuple(map(str,
                    (
                        n_records,
                        n_functions,
                        sum(durs)/len(durs),
                        min(durs),
                        max(durs),
                        errs,
                        rep+1
                    )
                )))
            if not cont: break

    results = "\n".join(
        ["# records,# functions,duration average,duration minimum, duration maximum,errors,repetitions"] + \
        [ ','.join(res) for res in results]
    )

    print(results)





let appsChart;

function fmt(bytes){ return (bytes/1024/1024).toFixed(1)+" MB"; }

function refreshStatus(){
    fetch("/api/status").then(r=>r.json()).then(d=>{
        cpu.innerText=d.cpu;
        ram.innerText=d.ram;
        storage.innerText=d.storage.percent+"%";
        storageText.innerText=fmt(d.storage.used)+" / "+fmt(d.storage.total);
        uptime.innerText=d.uptime;
    });
}

function refreshApps(){
    fetch("/api/apps-storage").then(r=>r.json()).then(d=>{
        const table = document.getElementById("appsTable");
        table.innerHTML="";
        let labels=[], data=[];
        d.apps.forEach(a=>{
            table.innerHTML += `<div class="row"><span>${a.name}</span><span>${fmt(a.size)} (${a.percent}%)</span></div>`;
            labels.push(a.name);
            data.push(a.size);
        });
        if(!appsChart){
            const ctx = document.getElementById("appsChart").getContext("2d");
            appsChart = new Chart(ctx, {
                type:'pie',
                data:{ labels: labels, datasets:[{data:data, backgroundColor:['#6366f1','#22d3ee','#facc15','#10b981','#f87171','#8b5cf6'] }] }
            });
        } else {
            appsChart.data.labels = labels;
            appsChart.data.datasets[0].data = data;
            appsChart.update();
        }
    });
}

function refreshLogs(){
    fetch("/api/logs").then(r=>r.json()).then(d=>logs.innerText=d.logs);
}

function restart(){ fetch("/api/restart",{method:"POST"}).then(()=>alert("Restarted")); }
function clearCache(){ fetch("/api/clear-cache",{method:"POST"}).then(()=>alert("Cache cleared")); }

setInterval(()=>{ refreshStatus(); refreshApps(); refreshLogs(); },5000);
refreshStatus(); refreshApps(); refreshLogs();
